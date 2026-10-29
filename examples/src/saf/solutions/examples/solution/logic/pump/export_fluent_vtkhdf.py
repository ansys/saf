# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0

"""Read ANSYS Fluent CFF case/data files and write VTKHDF.

``*.cas.h5`` holds the mesh. ``*.dat.h5`` holds the solution. VTK's
``vtkFLUENTCFFReader`` only pairs a case with a sibling named
``<case-stem>.dat.h5``, so numbered files such as ``elbow-2-00001.dat.h5`` are
read here directly.

A single data file is written as a multiblock VTKHDF file: one tetrahedral
fluid block plus triangle boundary blocks, or native mixed-cell volume zones
and polygon boundaries using VTK's Fluent reader. Multiple data files in time order
are written as one temporal VTKHDF file containing only the fluid volume
(VTKHDF time series do not support multiblock partitions).
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re

import h5py
import numpy as np
import vtk
from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray
from vtkmodules.util.vtkAlgorithm import VTKPythonAlgorithmBase

DATA_FILE_INDEX = re.compile(r"-(\d+)\.dat\.h5$", re.IGNORECASE)
LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1"

# Fluent CFF elementType for a uniform tetrahedral cell section.
TETRAHEDRON = 2
# Fluent face zone type for interior faces (legacy case-format thread type).
INTERIOR = 2

FIELD_NAMES = {
    "SV_P": "Pressure",
    "SV_T": "Temperature",
    "SV_H": "Enthalpy",
    "SV_K": "TurbulentKineticEnergy",
    "SV_D": "TurbulentDissipationRate",
    "SV_DENSITY": "Density",
    "SV_MU_LAM": "LaminarViscosity",
    "SV_MU_T": "TurbulentViscosity",
    "SV_BF_V": "BodyForce",
    "SV_DPM_PARTITION": "DpmPartition",
    "SV_FLUX": "MassFlux",
    "SV_HEAT_FLUX": "HeatFlux",
    "SV_HEAT_FLUX_SENSIBLE": "SensibleHeatFlux",
    "SV_RAD_HEAT_FLUX": "RadiationHeatFlux",
    "SV_DT_BC_SOURCE": "BoundaryEnergySource",
    "SV_MACH": "MachNumber",
    "SV_ARTIFICIAL_WALL_FLAG": "ArtificialWallFlag",
    "SV_WALL_SHEAR": "WallShearStress",
    "SV_WALL_V": "WallVelocity",
    "SV_WALL_VV": "WallVV",
    "SV_WALL_T_INNER": "InnerWallTemperature",
    "SV_WALL_YPLUS": "YPlus",
    "SV_WALL_YPLUS_UTAU": "YPlusUTau",
    "SV_WALL_PRORUS_ZONE_FORCE_MEAN": "PorousZoneForce",
}

FACE_ZONE_TYPES = {
    2: "interior",
    3: "wall",
    4: "pressure-inlet",
    5: "pressure-outlet",
    7: "symmetry",
    8: "periodic-shadow",
    9: "pressure-far-field",
    10: "velocity-inlet",
    12: "periodic",
    14: "fan",
    20: "mass-flow-inlet",
    24: "interface",
    31: "outflow",
    36: "outflow",
    37: "axis",
}

EXPORT_ORDER = (
    "SV_P",
    "SV_T",
    "SV_H",
    "SV_DENSITY",
    "SV_K",
    "SV_D",
    "SV_MU_LAM",
    "SV_MU_T",
    "SV_BF_V",
    "SV_DPM_PARTITION",
    "SV_FLUX",
    "SV_HEAT_FLUX",
    "SV_HEAT_FLUX_SENSIBLE",
    "SV_RAD_HEAT_FLUX",
    "SV_MACH",
    "SV_WALL_YPLUS",
    "SV_WALL_YPLUS_UTAU",
    "SV_WALL_SHEAR",
    "SV_WALL_V",
    "SV_WALL_VV",
    "SV_WALL_T_INNER",
    "SV_WALL_PRORUS_ZONE_FORCE_MEAN",
    "SV_DT_BC_SOURCE",
    "SV_ARTIFICIAL_WALL_FLAG",
)

VELOCITY_COMPONENTS = ("SV_U", "SV_V", "SV_W")


@dataclass(frozen=True)
class FaceZone:
    name: str
    zone_id: int
    zone_type: int
    min_id: int
    max_id: int

    @property
    def count(self) -> int:
        return self.max_id - self.min_id + 1

    @property
    def type_name(self) -> str:
        return FACE_ZONE_TYPES.get(self.zone_type, "unknown")


@dataclass(frozen=True)
class CellZone:
    name: str
    zone_id: int
    zone_type: int
    min_id: int
    max_id: int


@dataclass
class IndexedField:
    values: np.ndarray
    covered: np.ndarray

    def take(self, min_id: int, max_id: int) -> np.ndarray | None:
        if min_id < 1 or max_id > self.covered.size:
            return None
        slot = slice(min_id - 1, max_id)
        if not np.all(self.covered[slot]):
            return None
        return self.values[slot]


@dataclass
class FluentMesh:
    path: Path
    node_count: int
    face_count: int
    cell_count: int
    dimension: int
    coords: np.ndarray
    triangles: np.ndarray
    c0: np.ndarray
    c1: np.ndarray
    cell_zone: CellZone
    face_zones: list[FaceZone]


@dataclass(frozen=True)
class ResidualHistory:
    name: str
    active: int
    iterations: np.ndarray
    values: np.ndarray


@dataclass
class FluentSolution:
    path: Path
    solver: str
    version: str
    origin: str
    case_name: str
    data_variables: str
    cell_fields: dict[str, IndexedField]
    face_fields: dict[str, IndexedField]
    residuals: tuple[ResidualHistory, ...]


def scalar_attr(obj: h5py.Group | h5py.Dataset, name: str) -> int:
    value = np.asarray(obj.attrs[name]).reshape(-1)
    if value.size != 1:
        raise RuntimeError(f"{obj.name} attribute {name} is not a scalar")
    return int(value[0])


def dataset_text(dataset: h5py.Dataset) -> str:
    item = np.asarray(dataset[()]).reshape(-1)[0]
    if isinstance(item, (bytes, np.bytes_)):
        return bytes(item).decode("utf-8", "replace").split("\x00", 1)[0]
    return str(item)


def decode_names(dataset: h5py.Dataset) -> list[str]:
    text = dataset_text(dataset)
    return [part for part in text.split(";") if part]


def ensure_hdf5_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    header = path.read_bytes()[: max(len(LFS_POINTER_PREFIX), 8)]
    if header[: len(LFS_POINTER_PREFIX)] == LFS_POINTER_PREFIX:
        raise RuntimeError(
            f"{path} is a Git LFS pointer, not an HDF5 file. "
            "Install git-lfs and run `git lfs pull` in the example-data checkout."
        )
    if header[:4] != b"\x89HDF":
        raise RuntimeError(f"{path} does not look like an HDF5 file")


def case_prefix(case_path: Path) -> str:
    name = case_path.name
    if name.endswith(".cas.h5"):
        return name[: -len(".cas.h5")]
    if name.endswith(".cas"):
        return name[: -len(".cas")]
    return case_path.stem


def discover_case_file(directory: Path) -> Path:
    cases = sorted(directory.glob("*.cas.h5"))
    if not cases:
        raise FileNotFoundError(f"no *.cas.h5 file found in {directory}")
    if len(cases) > 1:
        names = ", ".join(path.name for path in cases)
        raise RuntimeError(f"multiple case files in {directory}: {names}")
    return cases[0]


def discover_data_files(case_path: Path, directory: Path) -> list[Path]:
    prefix = case_prefix(case_path)
    indexed: list[tuple[int, Path]] = []
    for path in sorted(directory.glob(f"{prefix}-*.dat.h5")):
        match = DATA_FILE_INDEX.search(path.name)
        if match is None:
            continue
        ensure_hdf5_file(path)
        indexed.append((int(match.group(1)), path))
    if not indexed:
        raise FileNotFoundError(f"no numbered {prefix}-*.dat.h5 files found in {directory}")
    indexed.sort(key=lambda item: item[0])
    return [path for _, path in indexed]


def flow_time_seconds(solution: FluentSolution) -> float:
    flow_time = scheme_number(solution.data_variables, "flow-time")
    if flow_time is None:
        match = DATA_FILE_INDEX.search(solution.path.name)
        if match is None:
            raise RuntimeError(f"could not determine time for {solution.path.name}")
        return float(match.group(1))
    return flow_time


def scheme_number(text: str, name: str) -> float | None:
    match = re.search(rf"\({re.escape(name)}\s+([-+0-9.eE]+)\)", text)
    if match is None:
        return None
    return float(match.group(1))


def read_sections(group: h5py.Group) -> list[tuple[int, int, np.ndarray]]:
    names = sorted((name for name in group if name.isdigit()), key=int)
    pieces: list[tuple[int, int, np.ndarray]] = []
    for name in names:
        dataset = group[name]
        if not isinstance(dataset, h5py.Dataset):
            raise RuntimeError(f"{dataset.name} is not a dataset")
        min_id = scalar_attr(dataset, "minId")
        max_id = scalar_attr(dataset, "maxId")
        values = np.asarray(dataset[()])
        expected = max_id - min_id + 1
        if values.shape[0] != expected:
            raise RuntimeError(f"{dataset.name} length {values.shape[0]} does not span ids {min_id}..{max_id}")
        pieces.append((min_id, max_id, values))
    if "nSections" in group.attrs and scalar_attr(group, "nSections") != len(pieces):
        raise RuntimeError(f"{group.name} nSections does not match the datasets present")
    if not pieces:
        raise RuntimeError(f"{group.name} has no numbered sections")
    return pieces


def stitch_sections(
    pieces: list[tuple[int, int, np.ndarray]],
    fill: float | int,
    dtype: np.dtype,
) -> tuple[np.ndarray, np.ndarray]:
    max_id = max(piece[1] for piece in pieces)
    tail = pieces[0][2].shape[1:]
    values = np.empty((max_id, *tail), dtype=dtype)
    values.fill(fill)
    covered = np.zeros(max_id, dtype=bool)
    for min_id, piece_max, data in pieces:
        slot = slice(min_id - 1, piece_max)
        if np.any(covered[slot]):
            raise RuntimeError("overlapping Fluent id sections")
        values[slot] = data
        covered[slot] = True
    return values, covered


def read_indexed_field(group: h5py.Group) -> IndexedField:
    pieces = read_sections(group)
    sample = pieces[0][2]
    if sample.dtype.kind == "f":
        values, covered = stitch_sections(pieces, np.nan, np.float32)
    else:
        values, covered = stitch_sections(pieces, 0, np.int64)
    return IndexedField(values, covered)


def read_face_triangles(faces: h5py.Group) -> np.ndarray:
    sections: list[tuple[int, int, np.ndarray, np.ndarray]] = []
    for name in sorted(faces["nodes"], key=int):
        section = faces["nodes"][name]
        min_id = scalar_attr(section, "minId")
        max_id = scalar_attr(section, "maxId")
        nnodes = np.asarray(section["nnodes"][()], dtype=np.int32)
        nodes = np.asarray(section["nodes"][()], dtype=np.int64)
        if nnodes.shape[0] != max_id - min_id + 1:
            raise RuntimeError(f"{section.name} nnodes length does not match its id range")
        if int(nnodes.sum()) != int(nodes.shape[0]):
            raise RuntimeError(f"{section.name} nodes length does not match nnodes")
        sections.append((min_id, max_id, nnodes, nodes))
    sections.sort()
    if sections[0][0] != 1:
        raise RuntimeError("face node ids do not start at 1")
    expected = 1
    for min_id, max_id, _, _ in sections:
        if min_id != expected:
            raise RuntimeError(f"gap in face node ids before {min_id}")
        expected = max_id + 1
    nnodes = np.concatenate([section[2] for section in sections])
    nodes = np.concatenate([section[3] for section in sections])
    if not np.all(nnodes == 3):
        raise RuntimeError("only triangular Fluent faces are supported")
    return nodes.reshape(-1, 3) - 1


def read_coords(nodes: h5py.Group) -> np.ndarray:
    pieces = read_sections(nodes["coords"])
    coords, covered = stitch_sections(pieces, np.nan, np.float64)
    if coords.ndim != 2 or coords.shape[1] != 3:
        raise RuntimeError(f"expected node coordinates of shape (N, 3), found {coords.shape}")
    if not np.all(covered) or not np.isfinite(coords).all():
        raise RuntimeError("node coordinate ids have a gap")
    return coords


def read_face_zones(topology: h5py.Group) -> list[FaceZone]:
    count = scalar_attr(topology, "nZones")
    names = decode_names(topology["name"])
    if len(names) != count:
        raise RuntimeError(f"face zone name count {len(names)} != nZones {count}")
    min_ids = np.asarray(topology["minId"][()], dtype=np.int64)
    max_ids = np.asarray(topology["maxId"][()], dtype=np.int64)
    zone_ids = np.asarray(topology["id"][()], dtype=np.int64)
    zone_types = np.asarray(topology["zoneType"][()], dtype=np.int64)
    zones = [
        FaceZone(
            name=names[index],
            zone_id=int(zone_ids[index]),
            zone_type=int(zone_types[index]),
            min_id=int(min_ids[index]),
            max_id=int(max_ids[index]),
        )
        for index in range(count)
    ]
    return zones


def read_cell_zone(topology: h5py.Group) -> CellZone:
    names = decode_names(topology["name"])
    if len(names) != 1:
        raise RuntimeError(f"expected one cell zone, found {names}")
    return CellZone(
        name=names[0],
        zone_id=int(np.asarray(topology["id"][()]).reshape(-1)[0]),
        zone_type=int(np.asarray(topology["zoneType"][()]).reshape(-1)[0]),
        min_id=int(np.asarray(topology["minId"][()]).reshape(-1)[0]),
        max_id=int(np.asarray(topology["maxId"][()]).reshape(-1)[0]),
    )


def require_uniform_tets(cells: h5py.Group, cell_count: int) -> None:
    pieces: list[tuple[int, int, int]] = []
    for name in sorted(cells["ctype"], key=int):
        section = cells["ctype"][name]
        pieces.append(
            (
                scalar_attr(section, "minId"),
                scalar_attr(section, "maxId"),
                scalar_attr(section, "elementType"),
            )
        )
    if pieces != [(1, cell_count, TETRAHEDRON)]:
        raise RuntimeError(f"only one tetrahedral cell section is supported, found {pieces}")


def load_mesh(path: Path) -> FluentMesh:
    ensure_hdf5_file(path)
    with h5py.File(path, "r") as handle:
        mesh_names = list(handle["meshes"])
        if mesh_names != ["1"]:
            raise RuntimeError(f"expected a single mesh group '1', found {mesh_names}")
        mesh = handle["meshes/1"]
        cell_count = scalar_attr(mesh, "cellCount")
        face_count = scalar_attr(mesh, "faceCount")
        node_count = scalar_attr(mesh, "nodeCount")
        dimension = scalar_attr(mesh, "dimension")
        require_uniform_tets(mesh["cells"], cell_count)
        coords = read_coords(mesh["nodes"])
        triangles = read_face_triangles(mesh["faces"])
        c0_field = read_indexed_field(mesh["faces"]["c0"])
        c1_field = read_indexed_field(mesh["faces"]["c1"])
        cell_zone = read_cell_zone(mesh["cells"]["zoneTopology"])
        face_zones = read_face_zones(mesh["faces"]["zoneTopology"])

    if dimension != 3:
        raise RuntimeError(f"expected a 3D mesh, found dimension {dimension}")
    if coords.shape[0] != node_count or triangles.shape[0] != face_count:
        raise RuntimeError("mesh attribute counts do not match coordinate or face arrays")
    if not np.all(c0_field.covered) or c0_field.values.shape[0] != face_count:
        raise RuntimeError("face owner cells (c0) do not cover every face")
    c0 = c0_field.values.astype(np.int64, copy=False)
    c1 = np.zeros(face_count, dtype=np.int64)
    c1[c1_field.covered] = c1_field.values[c1_field.covered]
    if np.any(c0 < 1) or np.any(c0 > cell_count):
        raise RuntimeError("c0 cell ids fall outside the cell range")
    if cell_zone.min_id != 1 or cell_zone.max_id != cell_count:
        raise RuntimeError("cell zone does not cover every cell")
    covered = np.zeros(face_count, dtype=bool)
    for zone in face_zones:
        slot = slice(zone.min_id - 1, zone.max_id)
        if zone.min_id < 1 or zone.max_id > face_count or np.any(covered[slot]):
            raise RuntimeError(f"face zone {zone.name} overlaps another zone or leaves the mesh")
        covered[slot] = True
    if not np.all(covered):
        raise RuntimeError("face zones do not cover every face")
    return FluentMesh(
        path=path,
        node_count=node_count,
        face_count=face_count,
        cell_count=cell_count,
        dimension=dimension,
        coords=coords,
        triangles=triangles,
        c0=c0,
        c1=c1,
        cell_zone=cell_zone,
        face_zones=face_zones,
    )


def tetrahedra_from_faces(mesh: FluentMesh) -> tuple[np.ndarray, int]:
    """Return 0-based tet connectivity and how many tets were flipped to a positive volume."""
    owners = mesh.c0 - 1
    interior = np.flatnonzero(mesh.c1 > 0)
    use_cells = np.concatenate((owners, mesh.c1[interior] - 1))
    use_faces = np.concatenate((mesh.triangles, mesh.triangles[interior]), axis=0)
    order = np.argsort(use_cells, kind="mergesort")
    use_faces = use_faces[order]
    counts = np.bincount(use_cells, minlength=mesh.cell_count)
    if use_faces.shape[0] != mesh.cell_count * 4 or not np.all(counts == 4):
        bad = np.flatnonzero(counts != 4)
        sample = (bad[:5] + 1).tolist()
        raise RuntimeError(f"{bad.size} cells do not have 4 triangular faces (ids {sample})")
    grouped = np.sort(use_faces.reshape(mesh.cell_count, 12), axis=1).reshape(mesh.cell_count, 4, 3)
    if not np.all(grouped[:, :, 0] == grouped[:, :, 1]) or not np.all(grouped[:, :, 1] == grouped[:, :, 2]):
        raise RuntimeError("faces incident to a cell do not close into a tetrahedron")
    tets = np.array(grouped[:, :, 0], dtype=np.int64, copy=True)
    if tets.min() < 0 or tets.max() >= mesh.node_count:
        raise RuntimeError("tetrahedron node ids fall outside the node range")
    volumes = tet_volumes(mesh.coords, tets)
    flipped = int(np.count_nonzero(volumes < 0.0))
    negative = volumes < 0.0
    if np.any(negative):
        hold = tets[negative, 2].copy()
        tets[negative, 2] = tets[negative, 3]
        tets[negative, 3] = hold
        volumes = tet_volumes(mesh.coords, tets)
    if np.any(volumes <= 0.0):
        raise RuntimeError("tetrahedron orientation still has a non-positive volume")
    return tets, flipped


def tet_volumes(coords: np.ndarray, tets: np.ndarray) -> np.ndarray:
    points = coords[tets]
    edge_a = points[:, 1] - points[:, 0]
    edge_b = points[:, 2] - points[:, 0]
    edge_c = points[:, 3] - points[:, 0]
    return np.einsum("ij,ij->i", edge_a, np.cross(edge_b, edge_c)) / 6.0


def load_solution(path: Path) -> FluentSolution:
    ensure_hdf5_file(path)
    with h5py.File(path, "r") as handle:
        steps = [name for name in handle["results"] if name != "residuals"]
        if steps != ["1"]:
            raise RuntimeError(f"expected a single steady result group '1', found {steps}")
        phases = list(handle["results/1"])
        if phases != ["phase-1"]:
            raise RuntimeError(f"expected a single phase-1 group, found {phases}")
        phase = handle["results/1/phase-1"]
        cell_fields = {
            name: read_indexed_field(group) for name, group in phase["cells"].items() if isinstance(group, h5py.Group)
        }
        face_fields = {
            name: read_indexed_field(group) for name, group in phase["faces"].items() if isinstance(group, h5py.Group)
        }
        residuals = []
        # A data file written right after initialisation has no iterations, hence no residual group.
        residual_groups = handle["results/residuals/phase-1"].items() if "residuals" in handle["results"] else []
        for name, group in residual_groups:
            residuals.append(
                ResidualHistory(
                    name=name,
                    active=scalar_attr(group, "isActive"),
                    iterations=np.asarray(group["iterations"][()]).reshape(-1).copy(),
                    values=np.asarray(group["data"][()]).copy(),
                )
            )
        return FluentSolution(
            path=path,
            solver=dataset_text(handle["settings/Solver"]),
            version=dataset_text(handle["settings/Version"]),
            origin=dataset_text(handle["settings/Origin"]),
            case_name=dataset_text(handle["settings/Case File"]),
            data_variables=dataset_text(handle["settings/Data Variables"]),
            cell_fields=cell_fields,
            face_fields=face_fields,
            residuals=tuple(residuals),
        )


def fixed_cell_array(connectivity: np.ndarray) -> vtk.vtkCellArray:
    count, width = connectivity.shape
    offsets = np.arange(0, (count + 1) * width, width, dtype=np.int64)
    cells = vtk.vtkCellArray()
    cells.SetData(
        numpy_to_vtkIdTypeArray(offsets, deep=True),
        numpy_to_vtkIdTypeArray(np.ascontiguousarray(connectivity, dtype=np.int64).ravel(), deep=True),
    )
    return cells


def add_vtk_array(
    data: vtk.vtkDataSetAttributes,
    name: str,
    values: np.ndarray,
    components: tuple[str, ...] | None = None,
) -> None:
    array = numpy_to_vtk(np.ascontiguousarray(values), deep=True)
    array.SetName(name)
    if components is not None and values.ndim == 2:
        for index, component in enumerate(components):
            array.SetComponentName(index, component)
    data.AddArray(array)


def add_scalar_field(data: vtk.vtkFieldData, name: str, value: float) -> None:
    array = vtk.vtkDoubleArray()
    array.SetName(name)
    array.InsertNextValue(float(value))
    data.AddArray(array)


def velocity_array(fields: dict[str, IndexedField], min_id: int, max_id: int) -> np.ndarray | None:
    if not all(name in fields for name in VELOCITY_COMPONENTS):
        return None
    chunks = [fields[name].take(min_id, max_id) for name in VELOCITY_COMPONENTS]
    if any(chunk is None for chunk in chunks):
        return None
    return np.column_stack(chunks).astype(np.float32, copy=False)


def attach_solution(
    cell_data: vtk.vtkCellData,
    fields: dict[str, IndexedField],
    min_id: int,
    max_id: int,
) -> list[str]:
    exported: list[str] = []
    skip: set[str] = set()
    velocity = velocity_array(fields, min_id, max_id)
    if velocity is not None:
        add_vtk_array(cell_data, "Velocity", velocity, ("U", "V", "W"))
        exported.append("Velocity")
        skip.update(VELOCITY_COMPONENTS)
    ordered = [name for name in EXPORT_ORDER if name in fields]
    ordered.extend(sorted(name for name in fields if name not in EXPORT_ORDER and name not in skip))
    for name in ordered:
        if name in skip:
            continue
        chunk = fields[name].take(min_id, max_id)
        if chunk is None:
            continue
        if chunk.dtype.kind == "f":
            chunk = np.ascontiguousarray(chunk, dtype=np.float32)
        components = ("X", "Y", "Z") if chunk.ndim == 2 and chunk.shape[1] == 3 else None
        vtk_name = FIELD_NAMES.get(name, name)
        add_vtk_array(cell_data, vtk_name, chunk, components)
        exported.append(vtk_name)
    if cell_data.HasArray("Pressure"):
        cell_data.SetActiveScalars("Pressure")
    if cell_data.HasArray("Velocity"):
        cell_data.SetActiveVectors("Velocity")
    return exported


def build_volume(
    mesh: FluentMesh,
    tets: np.ndarray,
    solution: FluentSolution,
) -> vtk.vtkUnstructuredGrid:
    grid = vtk.vtkUnstructuredGrid()
    points = vtk.vtkPoints()
    points.SetData(numpy_to_vtk(np.ascontiguousarray(mesh.coords), deep=True))
    grid.SetPoints(points)
    types = np.full(mesh.cell_count, vtk.VTK_TETRA, dtype=np.uint8)
    grid.SetCells(numpy_to_vtk(types, deep=True), fixed_cell_array(tets))
    cell_ids = np.arange(1, mesh.cell_count + 1, dtype=np.int32)
    add_vtk_array(grid.GetCellData(), "FluentCellId", cell_ids)
    attach_solution(grid.GetCellData(), solution.cell_fields, 1, mesh.cell_count)
    for name, key in (
        ("OperatingPressure", "operating-pressure"),
        ("FlowTime", "flow-time"),
        ("SolverTime", "solvertime"),
    ):
        value = scheme_number(solution.data_variables, key)
        if value is not None:
            add_scalar_field(grid.GetFieldData(), name, value)
    return grid


def build_surface(
    mesh: FluentMesh,
    zone: FaceZone,
    solution: FluentSolution,
) -> vtk.vtkPolyData:
    triangles = mesh.triangles[zone.min_id - 1 : zone.max_id]
    used, inverse = np.unique(triangles.ravel(), return_inverse=True)
    local = inverse.reshape(triangles.shape)
    surface = vtk.vtkPolyData()
    points = vtk.vtkPoints()
    points.SetData(numpy_to_vtk(np.ascontiguousarray(mesh.coords[used]), deep=True))
    surface.SetPoints(points)
    surface.SetPolys(fixed_cell_array(local))
    face_ids = np.arange(zone.min_id, zone.max_id + 1, dtype=np.int32)
    owners = mesh.c0[zone.min_id - 1 : zone.max_id].astype(np.int32, copy=False)
    add_vtk_array(surface.GetCellData(), "FluentFaceId", face_ids)
    add_vtk_array(surface.GetCellData(), "OwnerCellId", owners)
    attach_solution(surface.GetCellData(), solution.face_fields, zone.min_id, zone.max_id)
    return surface


def build_multiblock(
    mesh: FluentMesh,
    solution: FluentSolution,
    tets: np.ndarray,
) -> vtk.vtkMultiBlockDataSet:
    boundaries = [zone for zone in mesh.face_zones if zone.zone_type != INTERIOR]
    root = vtk.vtkMultiBlockDataSet()
    root.SetNumberOfBlocks(1 + len(boundaries))
    root.SetBlock(0, build_volume(mesh, tets, solution))
    root.GetMetaData(0).Set(vtk.vtkCompositeDataSet.NAME(), mesh.cell_zone.name)
    for index, zone in enumerate(boundaries, start=1):
        root.SetBlock(index, build_surface(mesh, zone, solution))
        root.GetMetaData(index).Set(vtk.vtkCompositeDataSet.NAME(), zone.name)
    return root


def write_vtkhdf(data: vtk.vtkDataObject, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = vtk.vtkHDFWriter()
    writer.SetFileName(str(path))
    writer.SetInputData(data)
    if writer.Write() != 1:
        raise RuntimeError(f"vtkHDFWriter failed to write {path}")


class TemporalVolumeSource(VTKPythonAlgorithmBase):
    def __init__(self, volumes: list[vtk.vtkUnstructuredGrid], times: list[float]) -> None:
        """Serve ``volumes[i]`` as the time step ``times[i]``."""
        super().__init__(nInputPorts=0, nOutputPorts=1, outputType="vtkPartitionedDataSet")
        self._volumes = volumes
        self._times = [float(value) for value in times]

    def RequestInformation(self, request, inInfo, outInfo) -> int:
        info = outInfo.GetInformationObject(0)
        executive = self.GetExecutive()
        for time_value in self._times:
            info.Append(executive.TIME_STEPS(), time_value)
        info.Append(executive.TIME_RANGE(), self._times[0])
        info.Append(executive.TIME_RANGE(), self._times[-1])
        return 1

    def RequestData(self, request, inInfo, outInfo) -> int:
        info = outInfo.GetInformationObject(0)
        executive = self.GetExecutive()
        requested_time = (
            info.Get(executive.UPDATE_TIME_STEP()) if info.Has(executive.UPDATE_TIME_STEP()) else self._times[0]
        )
        step_index = min(
            range(len(self._times)),
            key=lambda index: abs(self._times[index] - requested_time),
        )
        output = vtk.vtkPartitionedDataSet.GetData(outInfo)
        output.SetNumberOfPartitions(1)
        output.SetPartition(0, self._volumes[step_index])
        return 1


def write_temporal_vtkhdf(source: TemporalVolumeSource, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = vtk.vtkHDFWriter()
    writer.SetFileName(str(path))
    writer.SetInputConnection(source.GetOutputPort())
    writer.SetWriteAllTimeSteps(True)
    if writer.Write() != 1:
        raise RuntimeError(f"vtkHDFWriter failed to write {path}")


def verify_vtkhdf(path: Path, expected_names: list[str], cell_count: int, node_count: int) -> None:
    reader = vtk.vtkHDFReader()
    reader.SetFileName(str(path))
    reader.Update()
    output = reader.GetOutput()
    if output.GetNumberOfBlocks() != len(expected_names):
        raise RuntimeError("written VTKHDF block count does not match the Fluent zones")
    names = []
    for index in range(output.GetNumberOfBlocks()):
        metadata = output.GetMetaData(index)
        names.append(metadata.Get(vtk.vtkCompositeDataSet.NAME()) if metadata is not None else None)
    if names != expected_names:
        raise RuntimeError(f"VTKHDF block names {names} != {expected_names}")
    fluid = output.GetBlock(0)
    if fluid.GetNumberOfCells() != cell_count or fluid.GetNumberOfPoints() != node_count:
        raise RuntimeError("written fluid block does not match the Fluent mesh size")
    if fluid.GetCellData().GetArray("Pressure") is None:
        raise RuntimeError("written fluid block is missing Pressure")
    if fluid.GetCellData().GetArray("Velocity") is None:
        raise RuntimeError("written fluid block is missing Velocity")


def verify_temporal_vtkhdf(path: Path, times: list[float], cell_count: int, node_count: int) -> None:
    reader = vtk.vtkHDFReader()
    reader.SetFileName(str(path))
    reader.UpdateInformation()
    if reader.GetNumberOfSteps() != len(times):
        raise RuntimeError("written VTKHDF time step count does not match the Fluent data files")
    for step_index, expected_time in enumerate(times):
        reader.SetStep(step_index)
        reader.Update()
        fluid = reader.GetOutputDataObject(0)
        if fluid.IsA("vtkPartitionedDataSet"):
            if fluid.GetNumberOfPartitions() != 1:
                raise RuntimeError("expected a single partition in the temporal VTKHDF file")
            fluid = fluid.GetPartition(0)
        if fluid.GetNumberOfCells() != cell_count or fluid.GetNumberOfPoints() != node_count:
            raise RuntimeError(f"time step {step_index} does not match the Fluent mesh size")
        if fluid.GetCellData().GetArray("Pressure") is None:
            raise RuntimeError(f"time step {step_index} is missing Pressure")


def format_tree(path: Path) -> list[str]:
    lines = [f"  {path.name}"]
    with h5py.File(path, "r") as handle:

        def visit(name: str, obj: h5py.Group | h5py.Dataset) -> None:
            indent = "    " + "  " * name.count("/")
            if isinstance(obj, h5py.Dataset):
                lines.append(f"{indent}{name.split('/')[-1]}  {obj.dtype} {tuple(obj.shape)}")
                return
            attrs = []
            for key in obj.attrs:
                value = np.asarray(obj.attrs[key]).reshape(-1)
                if value.size != 1:
                    continue
                item = value[0]
                if isinstance(item, (bytes, np.bytes_)):
                    text = bytes(item).decode("utf-8", "replace")
                    if len(text) > 48:
                        continue
                    attrs.append(f"{key}={text}")
                else:
                    shown = item.item() if hasattr(item, "item") else item
                    attrs.append(f"{key}={shown}")
            suffix = f"  ({', '.join(attrs)})" if attrs else ""
            lines.append(f"{indent}{name.split('/')[-1]}/{suffix}")

        handle.visititems(visit)
    return lines


def format_field(name: str, field: IndexedField) -> str:
    covered = field.values[field.covered] if field.values.ndim == 1 else field.values[field.covered]
    finite = covered[np.isfinite(covered)] if covered.dtype.kind == "f" else covered
    if finite.size == 0:
        span = "empty"
    elif finite.ndim == 1:
        span = f"min {np.min(finite):.6g}  max {np.max(finite):.6g}"
    else:
        span = f"shape {finite.shape}  min {np.min(finite):.6g}  max {np.max(finite):.6g}"
    first = int(np.flatnonzero(field.covered)[0]) + 1
    last = int(np.flatnonzero(field.covered)[-1]) + 1
    label = FIELD_NAMES.get(name, name)
    exported = label if name not in VELOCITY_COMPONENTS else "Velocity"
    return f"  {name} -> {exported}  ids {first}..{last}  {span}"


def format_residuals(residuals: tuple[ResidualHistory, ...]) -> list[str]:
    lines = []
    for history in residuals:
        last = np.array2string(history.values[-1], precision=4, separator=", ")
        lines.append(
            f"  {history.name}: {history.iterations.size} samples, isActive={history.active}, "
            f"iterations {history.iterations[0]:.0f}..{history.iterations[-1]:.0f}, last {last}"
        )
    return lines


def print_mesh_summary(mesh: FluentMesh, volumes: np.ndarray, flipped: int) -> None:
    lower = mesh.coords.min(axis=0)
    upper = mesh.coords.max(axis=0)
    print(
        f"Mesh  nodes {mesh.node_count}  faces {mesh.face_count}  "
        f"cells {mesh.cell_count}  dimension {mesh.dimension}"
    )
    print(
        f"bounds  x [{lower[0]:.6g}, {upper[0]:.6g}]  "
        f"y [{lower[1]:.6g}, {upper[1]:.6g}]  z [{lower[2]:.6g}, {upper[2]:.6g}]"
    )
    print(
        f"cell zone {mesh.cell_zone.name} id {mesh.cell_zone.zone_id} "
        f"type {mesh.cell_zone.zone_type}  ids {mesh.cell_zone.min_id}..{mesh.cell_zone.max_id}  tetrahedra"
    )
    print(f"volume  min {volumes.min():.6g}  max {volumes.max():.6g}  " f"sum {volumes.sum():.6g}  flipped {flipped}")
    print("face zones")
    for zone in mesh.face_zones:
        role = "boundary" if zone.zone_type != INTERIOR else "interior, used to build tets"
        print(
            f"  {zone.name}  id {zone.zone_id}  type {zone.zone_type} ({zone.type_name})  "
            f"faces {zone.min_id}..{zone.max_id} ({zone.count})  {role}"
        )


def print_report(
    mesh: FluentMesh,
    solution: FluentSolution,
    volumes: np.ndarray,
    flipped: int,
    verbose: bool,
) -> None:
    variables = solution.data_variables
    flow_time = scheme_number(variables, "flow-time")
    operating = scheme_number(variables, "operating-pressure")
    solver_time = scheme_number(variables, "solvertime")
    case_match = re.search(r'\(case-file \. "([^"]+)"\)', variables)
    data_match = re.search(r'\(data-file \. "([^"]+)"\)', variables)
    print(f"{solution.solver} {solution.version}  ({solution.origin})")
    print(f"case {mesh.path.name}    data {solution.path.name}")
    if case_match or data_match:
        recorded_case = case_match.group(1) if case_match else "-"
        recorded_data = data_match.group(1) if data_match else "-"
        print(f"recorded paths: case {recorded_case}    data {recorded_data}")

    def show(value: float | None, spec: str) -> str:
        return "n/a" if value is None else format(value, spec)

    print(
        f"flow-time {show(flow_time, 'g')}    solvertime {show(solver_time, '.6g')}    "
        f"operating-pressure {show(operating, 'g')}"
    )
    print("Pressure is stored as Fluent SV_P and is not shifted by the operating pressure.")
    if verbose:
        print()
        print("HDF5 layout")
        for line in format_tree(mesh.path):
            print(line)
        for line in format_tree(solution.path):
            print(line)
    print()
    print_mesh_summary(mesh, volumes, flipped)
    if verbose:
        print()
        print("Cell fields")
        for name in sorted(solution.cell_fields):
            print(format_field(name, solution.cell_fields[name]))
        print("Face fields")
        for name in sorted(solution.face_fields):
            print(format_field(name, solution.face_fields[name]))
        print("Residuals (printed only; not written into the VTKHDF mesh)")
        for line in format_residuals(solution.residuals):
            print(line)


def print_time_series_summary(data_files: list[Path], times: list[float]) -> None:
    print("Time steps")
    for index, (path, time_value) in enumerate(zip(data_files, times, strict=True)):
        solution = load_solution(path)
        pressure = solution.cell_fields["SV_P"].values[solution.cell_fields["SV_P"].covered]
        temperature = solution.cell_fields["SV_T"].values[solution.cell_fields["SV_T"].covered]
        print(
            f"  [{index}] {path.name}  flow-time {time_value:g}  "
            f"Pressure [{pressure.min():.6g}, {pressure.max():.6g}]  "
            f"Temperature [{temperature.min():.6g}, {temperature.max():.6g}]"
        )


def array_names(data: vtk.vtkDataSetAttributes) -> list[str]:
    return [data.GetArrayName(index) for index in range(data.GetNumberOfArrays())]


def append_mixed_surfaces(
    case_path: Path,
    solution: FluentSolution,
    root: vtk.vtkMultiBlockDataSet,
) -> list[tuple[str, int]]:
    with h5py.File(case_path, "r") as handle:
        mesh = handle["meshes/1"]
        coords = read_coords(mesh["nodes"])
        faces = mesh["faces"]
        zones = read_face_zones(faces["zoneTopology"])
        sections = sorted(faces["nodes"].values(), key=lambda section: scalar_attr(section, "minId"))
        expected_id = 1
        widths_parts = []
        nodes_parts = []
        for section in sections:
            min_id, max_id = scalar_attr(section, "minId"), scalar_attr(section, "maxId")
            widths = np.asarray(section["nnodes"][()], dtype=np.int64).reshape(-1)
            nodes = np.asarray(section["nodes"][()], dtype=np.int64).reshape(-1) - 1
            if min_id != expected_id or widths.size != max_id - min_id + 1:
                raise RuntimeError("face node sections have gaps or invalid lengths")
            if np.any(widths < 0) or np.any((widths > 0) & (widths < 3)) or widths.sum() != nodes.size:
                raise RuntimeError("invalid Fluent polygon face connectivity")
            widths_parts.append(widths)
            nodes_parts.append(nodes)
            expected_id = max_id + 1
        widths = np.concatenate(widths_parts)
        nodes = np.concatenate(nodes_parts)
        owners = read_indexed_field(faces["c0"])
        if widths.size != scalar_attr(mesh, "faceCount") or nodes.min() < 0 or nodes.max() >= coords.shape[0]:
            raise RuntimeError("face connectivity does not match the mesh counts")
    offsets = np.concatenate(([0], np.cumsum(widths)))
    names = {root.GetMetaData(index).Get(vtk.vtkCompositeDataSet.NAME()) for index in range(root.GetNumberOfBlocks())}
    expected = []
    for zone in zones:
        if zone.zone_type == INTERIOR:
            continue
        start, end = zone.min_id - 1, zone.max_id
        zone_widths = widths[start:end]
        valid = zone_widths > 0
        if not np.any(valid):
            print(f"Skipping auxiliary face zone {zone.name}: no polygon faces")
            continue
        face_nodes = nodes[offsets[start] : offsets[end]][np.repeat(valid, zone_widths)]
        used, local = np.unique(face_nodes, return_inverse=True)
        local_offsets = np.concatenate(([0], np.cumsum(zone_widths[valid])))
        polygons = vtk.vtkCellArray()
        polygons.SetData(
            numpy_to_vtkIdTypeArray(local_offsets, deep=True),
            numpy_to_vtkIdTypeArray(local.astype(np.int64), deep=True),
        )
        surface = vtk.vtkPolyData()
        points = vtk.vtkPoints()
        points.SetData(numpy_to_vtk(np.ascontiguousarray(coords[used]), deep=True))
        surface.SetPoints(points)
        surface.SetPolys(polygons)
        face_ids = np.arange(zone.min_id, zone.max_id + 1, dtype=np.int64)[valid]
        owner_values = owners.take(zone.min_id, zone.max_id)
        if owner_values is None:
            raise RuntimeError(f"face zone {zone.name} has incomplete owner cell ids")
        add_vtk_array(surface.GetCellData(), "FluentFaceId", face_ids)
        add_vtk_array(surface.GetCellData(), "OwnerCellId", owner_values[valid])
        fields = {}
        for key, field in solution.face_fields.items():
            chunk = field.take(zone.min_id, zone.max_id)
            if chunk is not None:
                fields[key] = IndexedField(chunk[valid], np.ones(face_ids.size, dtype=bool))
        attach_solution(surface.GetCellData(), fields, 1, face_ids.size)
        name = zone.name if zone.name not in names else f"{zone.name}_{zone.zone_id}"
        names.add(name)
        index = root.GetNumberOfBlocks()
        root.SetBlock(index, surface)
        root.GetMetaData(index).Set(vtk.vtkCompositeDataSet.NAME(), name)
        expected.append((name, surface.GetNumberOfCells()))
        print(f"  {name}: {surface.GetNumberOfPoints()} points, {surface.GetNumberOfCells()} boundary faces")
    return expected


def export_mixed_single(
    case_path: Path,
    data_path: Path,
    output_path: Path,
    verbose: bool,
) -> Path:
    ensure_hdf5_file(case_path)
    solution = load_solution(data_path)
    if Path(solution.case_name).name != case_path.name:
        print(f"warning: data file references {solution.case_name}, reading {case_path.name}")
    with h5py.File(case_path, "r") as handle:
        topology = handle["meshes/1/cells/zoneTopology"]
        names = decode_names(topology["name"])
        min_ids = np.asarray(topology["minId"][()]).reshape(-1)
        max_ids = np.asarray(topology["maxId"][()]).reshape(-1)
        cell_types = np.asarray(topology["cellType"][()]).reshape(-1)
        node_count = scalar_attr(handle["meshes/1"], "nodeCount")
    reader = vtk.vtkFLUENTCFFReader()
    reader.SetFileName(str(case_path.resolve()))
    reader.Update()
    source = reader.GetOutput()
    if source.GetNumberOfBlocks() != len(names):
        raise RuntimeError("VTK Fluent reader block count does not match the cell zones")
    root = vtk.vtkMultiBlockDataSet()
    expected: list[tuple[str, int]] = []
    for index, name in enumerate(names):
        min_id, max_id = int(min_ids[index]), int(max_ids[index])
        grid = source.GetBlock(index)
        count = max_id - min_id + 1
        if int(cell_types[index]) == 8 and grid.GetNumberOfCells() == 0:
            print(f"Skipping auxiliary interface cell zone {name}: ids {min_id}..{max_id}")
            continue
        if grid.GetNumberOfCells() != count or grid.GetNumberOfPoints() != node_count:
            raise RuntimeError(f"VTK Fluent reader did not fully reconstruct cell zone {name}")
        grid.GetCellData().Initialize()
        add_vtk_array(grid.GetCellData(), "FluentCellId", np.arange(min_id, max_id + 1, dtype=np.int64))
        attach_solution(grid.GetCellData(), solution.cell_fields, min_id, max_id)
        if not grid.GetCellData().HasArray("Pressure") or not grid.GetCellData().HasArray("Velocity"):
            raise RuntimeError(f"cell zone {name} is missing complete Pressure or Velocity fields")
        for label, key in (
            ("OperatingPressure", "operating-pressure"),
            ("FlowTime", "flow-time"),
            ("SolverTime", "solvertime"),
        ):
            value = scheme_number(solution.data_variables, key)
            if value is not None:
                add_scalar_field(grid.GetFieldData(), label, value)
        block_index = root.GetNumberOfBlocks()
        root.SetBlock(block_index, grid)
        root.GetMetaData(block_index).Set(vtk.vtkCompositeDataSet.NAME(), name)
        expected.append((name, count))
        print(f"  {name}: {node_count} points, {count} cells, arrays {', '.join(array_names(grid.GetCellData()))}")
    if not expected:
        raise RuntimeError("the Fluent case contains no supported volume cell zones")
    expected_surfaces = append_mixed_surfaces(case_path, solution, root)
    if verbose:
        for path in (case_path, data_path):
            print("\n".join(format_tree(path)))
    write_vtkhdf(root, output_path)
    check = vtk.vtkHDFReader()
    check.SetFileName(str(output_path))
    check.Update()
    written = check.GetOutput()
    if written.GetNumberOfBlocks() != len(expected) + len(expected_surfaces):
        raise RuntimeError("written VTKHDF block count does not match the Fluent zones")
    for index, (name, count) in enumerate(expected):
        grid = written.GetBlock(index)
        if written.GetMetaData(index).Get(vtk.vtkCompositeDataSet.NAME()) != name or grid.GetNumberOfCells() != count:
            raise RuntimeError(f"written VTKHDF does not match cell zone {name}")
        for field in ("FluentCellId", "Pressure", "Velocity"):
            array = grid.GetCellData().GetArray(field)
            if array is None or array.GetNumberOfTuples() != count:
                raise RuntimeError(f"written cell zone {name} is missing {field}")
    for index, (name, count) in enumerate(expected_surfaces, start=len(expected)):
        surface = written.GetBlock(index)
        if (
            written.GetMetaData(index).Get(vtk.vtkCompositeDataSet.NAME()) != name
            or surface.GetNumberOfCells() != count
        ):
            raise RuntimeError(f"written VTKHDF does not match face zone {name}")
        for field in ("FluentFaceId", "OwnerCellId"):
            array = surface.GetCellData().GetArray(field)
            if array is None or array.GetNumberOfTuples() != count:
                raise RuntimeError(f"written face zone {name} is missing {field}")
    print(f"wrote {output_path}")
    return output_path


def export_single(
    case_path: Path,
    data_path: Path,
    output_path: Path,
    verbose: bool,
) -> Path:
    ensure_hdf5_file(case_path)
    with h5py.File(case_path, "r") as handle:
        mesh = handle["meshes/1"]
        sections = mesh["cells/ctype"]
        uniform_tets = (
            len(sections) == 1
            and scalar_attr(next(iter(sections.values())), "elementType") == TETRAHEDRON
            and scalar_attr(mesh["cells/zoneTopology"], "nZones") == 1
        )
    if not uniform_tets:
        return export_mixed_single(case_path, data_path, output_path, verbose)
    mesh = load_mesh(case_path)
    solution = load_solution(data_path)
    if Path(solution.case_name).name != case_path.name:
        print(f"warning: data file references {solution.case_name}, reading {case_path.name}")
    tets, flipped = tetrahedra_from_faces(mesh)
    volumes = tet_volumes(mesh.coords, tets)
    print_report(mesh, solution, volumes, flipped, verbose)
    block = build_multiblock(mesh, solution, tets)
    write_vtkhdf(block, output_path)
    boundaries = [zone for zone in mesh.face_zones if zone.zone_type != INTERIOR]
    expected = [mesh.cell_zone.name, *[zone.name for zone in boundaries]]
    verify_vtkhdf(output_path, expected, mesh.cell_count, mesh.node_count)

    print()
    print(f"wrote {output_path}")
    for index in range(block.GetNumberOfBlocks()):
        name = block.GetMetaData(index).Get(vtk.vtkCompositeDataSet.NAME())
        dataset = block.GetBlock(index)
        print(
            f"  {name}: {dataset.GetNumberOfPoints()} points, {dataset.GetNumberOfCells()} cells, "
            f"arrays {', '.join(array_names(dataset.GetCellData()))}"
        )
    print("ParaView: open the file, select the fluid block, and color by Pressure or Velocity.")
    return output_path


def export_time_series(
    case_path: Path,
    data_paths: list[Path],
    output_path: Path,
    verbose: bool,
) -> Path:
    mesh = load_mesh(case_path)
    tets, flipped = tetrahedra_from_faces(mesh)
    volumes = tet_volumes(mesh.coords, tets)
    print(f"case {case_path}")
    print_mesh_summary(mesh, volumes, flipped)
    print()
    times = [flow_time_seconds(load_solution(path)) for path in data_paths]
    print_time_series_summary(data_paths, times)
    if verbose:
        print_report(mesh, load_solution(data_paths[0]), volumes, flipped, verbose=True)

    fluid_blocks: list[vtk.vtkUnstructuredGrid] = []
    for data_path in data_paths:
        solution = load_solution(data_path)
        if Path(solution.case_name).name != case_path.name:
            print(f"warning: {data_path.name} references {solution.case_name}, reading {case_path.name}")
        fluid_blocks.append(build_volume(mesh, tets, solution))

    print()
    print(
        "Writing temporal VTKHDF with the fluid volume only "
        "(boundary zones are omitted because VTKHDF time series require one dataset per step)."
    )
    write_temporal_vtkhdf(TemporalVolumeSource(fluid_blocks, times), output_path)
    verify_temporal_vtkhdf(output_path, times, mesh.cell_count, mesh.node_count)

    print()
    print(
        f"wrote {output_path} ({mesh.node_count} points, {mesh.cell_count} cells, "
        f"{len(times)} time steps from {times[0]:g} to {times[-1]:g})"
    )
    print(f"arrays {', '.join(array_names(fluid_blocks[0].GetCellData()))}")
    print("ParaView: color by Pressure or Velocity and use the time controls.")
    return output_path


def resolve_inputs(args: argparse.Namespace) -> tuple[Path, list[Path]]:
    if args.results_dir is not None:
        results_dir = args.results_dir.resolve()
        case_path = args.case.resolve() if args.case is not None else discover_case_file(results_dir)
        if args.data is not None:
            data_paths = [args.data.resolve()]
        else:
            data_paths = discover_data_files(case_path, results_dir)
        return case_path, data_paths

    if args.case is None or args.data is None:
        raise SystemExit("provide --results-dir or both --case and --data")

    case_path = args.case.resolve()
    if args.data.is_dir():
        data_paths = discover_data_files(case_path, args.data.resolve())
    else:
        data_paths = [args.data.resolve()]
    return case_path, data_paths


def parse_args() -> argparse.Namespace:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=None,
        help="directory containing one *.cas.h5 and numbered *.dat.h5 files",
    )
    parser.add_argument("--case", type=Path, default=None, help="Fluent CFF case file")
    parser.add_argument(
        "--data",
        type=Path,
        default=None,
        help="Fluent CFF data file, or a directory of numbered *.dat.h5 files",
    )
    parser.add_argument("--output", type=Path, default=None, help="output VTKHDF path")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print full HDF5 layout and field summaries",
    )
    return parser.parse_args()


def default_output(case_path: Path, data_paths: list[Path], here: Path) -> Path:
    prefix = case_prefix(case_path)
    output_dir = here / "output"
    if len(data_paths) == 1:
        data_name = data_paths[0].name.removesuffix(".dat.h5")
        return output_dir / f"{data_name}.vtkhdf"
    return output_dir / f"{prefix}_transient.vtkhdf"


def main() -> None:
    args = parse_args()
    here = Path(__file__).resolve().parent
    case_path, data_paths = resolve_inputs(args)
    output_path = args.output.resolve() if args.output is not None else default_output(case_path, data_paths, here)
    if len(data_paths) == 1:
        export_single(case_path, data_paths[0], output_path, args.verbose)
    else:
        export_time_series(case_path, data_paths, output_path, args.verbose)


if __name__ == "__main__":
    main()
