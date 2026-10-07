# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Ansys Geometry and Mesh Operations for Airfoil Analysis."""

import logging

from ansys.geometry.core.designer import Design
from ansys.geometry.core.math import Plane, Point2D, Point3D

# Geometry service imports
from ansys.geometry.core.misc import UNITS, Distance
from ansys.geometry.core.misc.options import TessellationOptions
from ansys.geometry.core.sketch import Sketch
import numpy as np
from scipy.interpolate import griddata
from vtkmodules.vtkCommonCore import vtkFloatArray, vtkPoints
from vtkmodules.vtkCommonDataModel import vtkCellArray, vtkPolyData
from vtkmodules.vtkIOXML import vtkXMLPolyDataReader, vtkXMLPolyDataWriter

# Local imports
from .airfoil import airfoil_surface
from .parameters import AirfoilParameters

logger = logging.getLogger(__name__)


def create_airfoil_sketch(
    camber_max: float,
    camber_pos: float,
    thickness_max: float,
    chord_length: float,
    max_points: int = 50,
) -> Sketch:
    """Create a 2D airfoil sketch from airfoil parameters.

    Parameters
    ----------
    camber_max : float
        Maximum camber of the airfoil (as fraction of chord)
    camber_pos : float
        Position of maximum camber (as fraction of chord)
    thickness_max : float
        Maximum thickness of the airfoil (as fraction of chord)
    chord_length : float
        Chord length in meters
    max_points : int, optional
        Maximum number of points to use for the airfoil profile (default: 50)

    Returns
    -------
    Sketch
        Ansys Geometry sketch containing the airfoil profile

    """
    logger.info("Creating airfoil sketch")

    airfoil = AirfoilParameters(
        x_coord=np.linspace(0, 1, 101),
        camber_max=camber_max,
        camber_pos=camber_pos,
        thickness_max=thickness_max,
        chord_length=chord_length,
    )

    xU, yU = airfoil_surface(
        airfoil.x_coord, airfoil.thickness_max, +1, airfoil.camber_max, airfoil.camber_pos, airfoil.chord_length
    )
    xL, yL = airfoil_surface(
        airfoil.x_coord, airfoil.thickness_max, -1, airfoil.camber_max, airfoil.camber_pos, airfoil.chord_length
    )

    # Create a plane for the sketch (XY plane)
    origin = Point3D([0, 0, 0])
    plane = Plane(origin, direction_x=[1, 0, 0], direction_y=[0, 1, 0])

    # Create airfoil sketch on the XY plane
    sketch = Sketch(plane)

    profile_points = []

    for i in range(len(xU) - 1, -1, -1):  # Reverse order for proper orientation
        profile_points.append(Point2D([xU[i], yU[i]], UNITS.m))

    for i in range(1, len(xL)):
        profile_points.append(Point2D([xL[i], yL[i]], UNITS.m))

    logger.info("Created %d airfoil profile points", len(profile_points))

    # Create the actual airfoil geometry
    try:
        # Reduce number of points to avoid geometry issues
        simplified_points = []
        step = max(1, len(profile_points) // max_points)
        for i in range(0, len(profile_points), step):
            simplified_points.append(profile_points[i])
        # Make sure we include the last point to close the shape
        if len(simplified_points) > 0 and simplified_points[-1] != profile_points[-1]:
            simplified_points.append(profile_points[-1])

        logger.info("Simplified to %d points", len(simplified_points))

        # Create segments individually (more reliable than fluent interface)
        for i in range(len(simplified_points) - 1):
            sketch.segment(simplified_points[i], simplified_points[i + 1])

        logger.info("Created airfoil sketch using individual segments")
        return sketch

    except Exception:
        logger.exception("Airfoil sketch creation failed")


def extrude_sketch_to_body(design: Design, sketch: Sketch, wing_span: float, body_name: str = "wing_body") -> object:
    """Extrude a 2D sketch to create a 3D body.

    Parameters
    ----------
    design : Design
        Ansys Geometry design object
    sketch : Sketch
        2D sketch to extrude
    wing_span : float
        Extrusion distance (wing span) in meters
    body_name : str, optional
        Name for the extruded body (default: "wing_body")

    Returns
    -------
    object
        Extruded 3D body object

    """
    logger.info("Extruding sketch to 3D body with span: %s m", wing_span)

    # Define wing parameters
    extrusion_distance = Distance(wing_span, UNITS.m)

    # Extrude the airfoil sketch to create the 3D wing
    wing_body = design.extrude_sketch(body_name, sketch, extrusion_distance)

    if not wing_body:
        raise RuntimeError("Wing body was not created during extrusion.")

    logger.info("Created 3D wing body: %s", wing_body)
    return wing_body


def tessellate_body(
    body: object,
) -> object:
    """Tessellate a 3D body to create a surface mesh.

    Parameters
    ----------
    body : object
        3D body to tessellate
    mesh_refinement : str, optional
        Mesh refinement level: "Coarse", "Medium", or "Fine" (default: "Medium")
    backend_version : tuple, optional
        Geometry service backend version as (major, minor, patch) tuple

    Returns
    -------
    object
        Tessellated surface mesh (VTK PolyData)

    Notes
    -----
    Tessellation options require geometry service v25.2.0+. For older versions,
    mesh refinement parameters will be ignored and a default coarse mesh is returned.
    """
    tess_options = TessellationOptions(
        surface_deviation=1e-4, angle_deviation=0.01, max_edge_length=0.01, max_aspect_ratio=1.0, watertight=False
    )

    # Tessellate the body to create surface mesh
    try:
        surface_mesh = body.tessellate(merge=True, tess_options=tess_options)
        logger.info(
            "Surface mesh generated with %d points and %d cells",
            surface_mesh.GetNumberOfPoints(),
            surface_mesh.GetNumberOfCells(),
        )

        return surface_mesh

    except Exception as e:
        logger.exception("Surface mesh generation failed")
        raise RuntimeError(f"Failed to tessellate body: {e}") from e


def save_to_vtk(mesh: object, output_file: str) -> None:
    """Save a VTK PolyData mesh to a .vtp file.

    Parameters
    ----------
    mesh : object
        VTK PolyData mesh to save
    output_file : str
        Path to output .vtp file

    Raises
    ------
    RuntimeError
        If saving the mesh fails
    """
    from vtkmodules.vtkIOXML import vtkXMLPolyDataWriter

    logger.info("Saving surface mesh to VTK file: %s", output_file)

    try:
        writer = vtkXMLPolyDataWriter()
        writer.SetFileName(output_file)
        writer.SetInputData(mesh)
        writer.Write()
    except Exception as e:
        logger.exception("Failed to save mesh")
        raise RuntimeError(f"Failed to save mesh to VTK file: {e}") from e


def create_airfoil_geometry_pipeline(
    modeler: object,
    camber_max: float,
    camber_pos: float,
    thickness_max: float,
    chord_length: float,
    wing_span: float,
    design_name: str = "AirfoilWing",
    max_sketch_points: int = 50,
    vtk_out_path: str = "airfoil_surface_mesh.vtp",
):
    """Complete pipeline to create airfoil geometry and mesh.

    Parameters
    ----------
    modeler : object
        Ansys Geometry modeler instance
    camber_max : float
        Maximum camber of the airfoil (as fraction of chord)
    camber_pos : float
        Position of maximum camber (as fraction of chord)
    thickness_max : float
        Maximum thickness of the airfoil (as fraction of chord)
    chord_length : float
        Chord length in meters
    wing_span : float
        Wing span in meters
    design_name : str, optional
        Name for the design (default: "AirfoilWing")
    max_sketch_points : int, optional
        Maximum points for sketch simplification (default: 50)
    vtk_out_path : str, optional
        Path for output VTK file (default: "airfoil_surface_mesh.vtp")
    """
    logger.info("Starting airfoil geometry creation pipeline")

    # Create design
    design = modeler.create_design(design_name)
    logger.info("Created design: %s", design_name)

    # Create sketch
    sketch = create_airfoil_sketch(
        camber_max=camber_max,
        camber_pos=camber_pos,
        thickness_max=thickness_max,
        chord_length=chord_length,
        max_points=max_sketch_points,
    )

    # Extrude to 3D body
    wing_body = extrude_sketch_to_body(design=design, sketch=sketch, wing_span=wing_span)

    # Tessellate for mesh
    surface_mesh = tessellate_body(
        body=wing_body,
    )

    save_to_vtk(surface_mesh, vtk_out_path)
    logger.info("Airfoil geometry pipeline complete")
    logger.info("3D wing created with span: %s m", wing_span)
    logger.info(
        "Surface mesh: %d points, %d cells",
        surface_mesh.GetNumberOfPoints(),
        surface_mesh.GetNumberOfCells(),
    )


def create_streamlines_vtp(x, y, stream, output_path):
    """Create a 2D VTP file using the actual computational grid.

    This function creates a VTK PolyData file using the original curvilinear
    computational grid (C-grid or O-grid) with the streamline field data.
    The airfoil boundary is extracted from the first column of the grid.

    Args:
        x (np.ndarray or list): Grid x-coordinates (Nxi × Neta)
        y (np.ndarray or list): Grid y-coordinates (Nxi × Neta)
        stream (list or np.ndarray): Stream function values (Nxi × Neta)
        output_path (str): Path to save the output VTP file

    Returns:
        str: Path to the created VTP file
    """
    # Convert inputs to numpy arrays if they are lists
    x = np.array(x) if isinstance(x, list) else x
    y = np.array(y) if isinstance(y, list) else y
    stream = np.array(stream) if isinstance(stream, list) else stream

    # Get grid dimensions (Nxi × Neta)
    Nxi, Neta = x.shape

    # Create VTK points and stream function array
    points = vtkPoints()
    stream_array = vtkFloatArray()
    stream_array.SetName("StreamFunction")

    # Add all grid points with their stream function values
    point_id_map = {}
    for i in range(Nxi):
        for j in range(Neta):
            point_id = i * Neta + j
            points.InsertNextPoint(x[i, j], y[i, j], 0.0)
            stream_array.InsertNextValue(stream[i, j])
            point_id_map[(i, j)] = point_id

    # Create quad cells for the computational grid
    grid_cells = vtkCellArray()

    for i in range(Nxi - 1):
        for j in range(Neta - 1):
            # Create a quad cell connecting adjacent grid points
            p0 = point_id_map[(i, j)]
            p1 = point_id_map[(i, j + 1)]
            p2 = point_id_map[(i + 1, j + 1)]
            p3 = point_id_map[(i + 1, j)]

            grid_cells.InsertNextCell(4)
            grid_cells.InsertCellPoint(p0)
            grid_cells.InsertCellPoint(p1)
            grid_cells.InsertCellPoint(p2)
            grid_cells.InsertCellPoint(p3)

    # Create airfoil boundary line (first column: x[:, 0], y[:, 0])
    # Also create as a filled polygon for visibility
    airfoil_polygon = vtkCellArray()
    airfoil_polygon.InsertNextCell(Nxi)
    for i in range(Nxi):
        airfoil_polygon.InsertCellPoint(point_id_map[(i, 0)])

    # Add airfoil polygon to grid cells
    for i in range(Nxi):
        grid_cells.InsertNextCell(1)
        grid_cells.InsertCellPoint(point_id_map[(i, 0)])

    # Create polydata with both grid and airfoil
    polydata = vtkPolyData()
    polydata.SetPoints(points)
    polydata.SetPolys(grid_cells)
    polydata.GetPointData().AddArray(stream_array)
    polydata.GetPointData().SetActiveScalars("StreamFunction")

    # Write to VTP file
    writer = vtkXMLPolyDataWriter()
    writer.SetFileName(str(output_path))
    writer.SetInputData(polydata)
    writer.Write()

    n_points = points.GetNumberOfPoints()
    n_cells = grid_cells.GetNumberOfCells()
    logger.info("Created computational grid VTP with %d points, %d cells: %s", n_points, n_cells, output_path)

    return str(output_path)


def create_streamlines_interpolated_vtp(x, y, stream, output_path):
    """Create a 2D VTP file with rectangular Cartesian grid and airfoil boundary.

    This function creates a VTK PolyData file by interpolating the curvilinear
    computational grid onto a rectangular Cartesian grid (like plot_streamlines),
    then creates quad cells for visualization. Cells inside the airfoil are excluded
    to create a hollow hole. The airfoil boundary is added as a line.

    Args:
        x (np.ndarray or list): Grid x-coordinates (Nxi × Neta) - airfoil at j=0
        y (np.ndarray or list): Grid y-coordinates (Nxi × Neta) - airfoil at j=0
        stream (list or np.ndarray): Stream function values (Nxi × Neta)
        output_path (str): Path to save the output VTP file

    Returns:
        str: Path to the created VTP file
    """
    from matplotlib.path import Path as MplPath

    # Convert inputs to numpy arrays if they are lists
    x = np.array(x) if isinstance(x, list) else x
    y = np.array(y) if isinstance(y, list) else y
    stream = np.array(stream) if isinstance(stream, list) else stream

    # Extract airfoil boundary (first column j=0)
    x_airfoil = x[:, 0]
    y_airfoil = y[:, 0]
    airfoil_path = MplPath(np.column_stack([x_airfoil, y_airfoil]))

    # Flatten the curvilinear grid for interpolation
    pts = np.column_stack([x.ravel(), y.ravel()])
    vals = stream.ravel()

    # Create non-uniform rectangular grid with refinement near airfoil
    # Determine airfoil bounding box
    x_airfoil_min, x_airfoil_max = x_airfoil.min(), x_airfoil.max()
    y_airfoil_min, y_airfoil_max = y_airfoil.min(), y_airfoil.max()
    airfoil_margin = 0.3  # Refinement zone around airfoil

    # Define domain
    x_min, x_max = -2, 3
    y_min, y_max = -1.5, 1.5

    # Create non-uniform spacing in x
    nx_total = 150
    # Fine spacing near airfoil
    x_fine = np.linspace(x_airfoil_min - airfoil_margin, x_airfoil_max + airfoil_margin, 80)
    # Coarse spacing outside
    x_left = np.linspace(x_min, x_airfoil_min - airfoil_margin, 30)
    x_right = np.linspace(x_airfoil_max + airfoil_margin, x_max, 40)
    xi = np.concatenate([x_left[:-1], x_fine, x_right[1:]])
    xi = np.sort(xi)

    # Create non-uniform spacing in y
    ny_total = 120
    # Fine spacing near airfoil
    y_fine = np.linspace(y_airfoil_min - airfoil_margin, y_airfoil_max + airfoil_margin, 60)
    # Coarse spacing outside
    y_bottom = np.linspace(y_min, y_airfoil_min - airfoil_margin, 30)
    y_top = np.linspace(y_airfoil_max + airfoil_margin, y_max, 30)
    yi = np.concatenate([y_bottom[:-1], y_fine, y_top[1:]])
    yi = np.sort(yi)

    XI, YI = np.meshgrid(xi, yi)

    # Interpolate stream function onto rectangular grid
    ZI = griddata(pts, vals, (XI, YI), method="cubic")

    # Get grid dimensions
    ny, nx = XI.shape

    # Create VTK points and stream function array
    points = vtkPoints()
    stream_array = vtkFloatArray()
    stream_array.SetName("StreamFunction")

    # Build a mapping from (j,i) to point ID, handling NaN values
    point_id_map = {}
    point_counter = 0

    for j in range(ny):
        for i in range(nx):
            if not np.isnan(ZI[j, i]):
                points.InsertNextPoint(XI[j, i], YI[j, i], 0.0)
                stream_array.InsertNextValue(ZI[j, i])
                point_id_map[(j, i)] = point_counter
                point_counter += 1

    # Create quad cells for the rectangular grid, but exclude cells inside airfoil
    grid_cells = vtkCellArray()
    n_filtered = 0

    for j in range(ny - 1):
        for i in range(nx - 1):
            # Check if all four corners exist (not NaN)
            p0 = (j, i)
            p1 = (j, i + 1)
            p2 = (j + 1, i + 1)
            p3 = (j + 1, i)

            if all(p in point_id_map for p in [p0, p1, p2, p3]):
                # Calculate cell centroid
                centroid_x = (XI[j, i] + XI[j, i + 1] + XI[j + 1, i + 1] + XI[j + 1, i]) / 4.0
                centroid_y = (YI[j, i] + YI[j, i + 1] + YI[j + 1, i + 1] + YI[j + 1, i]) / 4.0

                # Skip cell if centroid is inside airfoil
                if airfoil_path.contains_point([centroid_x, centroid_y]):
                    n_filtered += 1
                    continue

                # Create a quad cell
                grid_cells.InsertNextCell(4)
                grid_cells.InsertCellPoint(point_id_map[p0])
                grid_cells.InsertCellPoint(point_id_map[p1])
                grid_cells.InsertCellPoint(point_id_map[p2])
                grid_cells.InsertCellPoint(point_id_map[p3])

    # Add airfoil boundary from original grid (x[:, 0], y[:, 0])
    airfoil_start_id = points.GetNumberOfPoints()
    Nxi = x.shape[0]

    for i in range(Nxi):
        points.InsertNextPoint(x[i, 0], y[i, 0], 0.0)
        stream_array.InsertNextValue(stream[i, 0])

    # Create airfoil boundary line
    airfoil_line = vtkCellArray()
    airfoil_line.InsertNextCell(Nxi + 1)  # +1 to close the loop
    for i in range(Nxi):
        airfoil_line.InsertCellPoint(airfoil_start_id + i)
    # Close the loop
    airfoil_line.InsertCellPoint(airfoil_start_id)

    # Also add airfoil points as vertices for better visibility
    airfoil_verts = vtkCellArray()
    for i in range(Nxi):
        airfoil_verts.InsertNextCell(1)
        airfoil_verts.InsertCellPoint(airfoil_start_id + i)

    # Create polydata with grid, airfoil line, and airfoil vertices
    polydata = vtkPolyData()
    polydata.SetPoints(points)
    polydata.SetPolys(grid_cells)
    polydata.SetLines(airfoil_line)
    polydata.SetVerts(airfoil_verts)
    polydata.GetPointData().AddArray(stream_array)
    polydata.GetPointData().SetActiveScalars("StreamFunction")

    # Write to VTP file
    writer = vtkXMLPolyDataWriter()
    writer.SetFileName(str(output_path))
    writer.SetInputData(polydata)
    writer.Write()

    n_points = points.GetNumberOfPoints()
    n_cells = grid_cells.GetNumberOfCells()
    logger.info(
        "Created rectangular grid VTP with %d points, %d quad cells (filtered %d inside airfoil): %s",
        n_points,
        n_cells,
        n_filtered,
        output_path,
    )

    return str(output_path)


def map_2d_flow_to_3d_mesh(
    x, y, stream, input_vtp_path, output_vtp_path, chord_length: float = 1.0, Vinf: float = 1.0
) -> str:
    """Map 2D potential flow solution results onto 3D surface mesh loaded from VTP file.

    This function loads a VTK PolyData mesh from an input VTP file, maps the 2D flow
    solution data (computed from stream function) onto the mesh points, and saves
    the result to an output VTP file.

    Parameters
    ----------
    x : np.ndarray or list
        Grid x-coordinates (Nxi × Neta) - airfoil at j=0
    y : np.ndarray or list
        Grid y-coordinates (Nxi × Neta) - airfoil at j=0
    stream : list or np.ndarray
        Stream function values (Nxi × Neta)
    input_vtp_path : str
        Path to the input VTP file containing the 3D surface mesh
    output_vtp_path : str
        Path to save the output VTP file with mapped flow data
    chord_length : float, optional
        Actual chord length in meters for denormalizing coordinates (default: 1.0)
    Vinf : float, optional
        Freestream velocity for pressure coefficient calculation (default: 1.0)

    Returns
    -------
    str
        Path to the created output VTP file

    Notes
    -----
    Assumes the 3D mesh represents an extruded airfoil where:
    - X-coordinate corresponds to chordwise direction
    - Y-coordinate corresponds to thickness direction
    - Z-coordinate corresponds to spanwise direction (uniform field values)

    Maps the following calculated quantities: pressure_coefficient, u_velocity,
    v_velocity, velocity_magnitude, stream_function
    """
    # Convert inputs to numpy arrays if they are lists
    x = np.array(x) if isinstance(x, list) else x
    y = np.array(y) if isinstance(y, list) else y
    stream = np.array(stream) if isinstance(stream, list) else stream

    # Load the VTP file
    reader = vtkXMLPolyDataReader()
    reader.SetFileName(str(input_vtp_path))
    reader.Update()
    mesh = reader.GetOutput()

    if mesh is None:
        raise ValueError(f"Failed to load VTP file: {input_vtp_path}")

    # Compute velocity components from stream function
    # u = ∂ψ/∂y, v = -∂ψ/∂x
    u = np.zeros_like(stream)
    v = np.zeros_like(stream)

    # Central differences for interior points
    u[1:-1, 1:-1] = (stream[1:-1, 2:] - stream[1:-1, :-2]) / (y[1:-1, 2:] - y[1:-1, :-2])
    v[1:-1, 1:-1] = -(stream[2:, 1:-1] - stream[:-2, 1:-1]) / (x[2:, 1:-1] - x[:-2, 1:-1])

    # Forward/backward differences at boundaries
    u[:, 0] = (stream[:, 1] - stream[:, 0]) / (y[:, 1] - y[:, 0])
    u[:, -1] = (stream[:, -1] - stream[:, -2]) / (y[:, -1] - y[:, -2])
    v[0, :] = -(stream[1, :] - stream[0, :]) / (x[1, :] - x[0, :])
    v[-1, :] = -(stream[-1, :] - stream[-2, :]) / (x[-1, :] - x[-2, :])

    # Compute velocity magnitude and pressure coefficient
    velocity_mag = np.sqrt(u**2 + v**2)
    # Pressure coefficient: Cp = 1 - (V/Vinf)^2
    Cp = 1.0 - (velocity_mag / Vinf) ** 2

    # Extract mesh points
    points = mesh.GetPoints()
    num_points = points.GetNumberOfPoints()

    # Create points array for interpolation (N, 2)
    grid_points = np.column_stack((x.ravel(), y.ravel()))

    # Define the fields to map directly from computed quantities
    fields_to_map = {
        "pressure_coefficient": Cp,
        "u_velocity": u,
        "v_velocity": v,
        "velocity_magnitude": velocity_mag,
        "stream_function": stream,
    }

    logger.info("Mapping fields: %s", list(fields_to_map.keys()))

    # Process each field in the 3D mesh
    for field_name, field_2d in fields_to_map.items():
        field_values = field_2d.flatten()  # Flatten 2D field to 1D for interpolation

        # Create target points for interpolation (project 3D points to 2D)
        target_points = np.zeros((num_points, 2))
        for i in range(num_points):
            point = points.GetPoint(i)
            # Project 3D point to 2D coordinates
            x_proj = point[0] / chord_length  # Normalize by chord length
            y_proj = point[1]  # Thickness coordinate
            target_points[i] = [x_proj, y_proj]

        # Perform interpolation using griddata
        try:
            interpolated_values = griddata(
                points=grid_points, values=field_values, xi=target_points, method="linear", fill_value=0.0
            )

            # Add interpolated field to mesh as point data
            from vtkmodules.vtkCommonCore import vtkDoubleArray

            field_array = vtkDoubleArray()
            field_array.SetName(field_name)
            field_array.SetNumberOfComponents(1)
            field_array.SetNumberOfTuples(num_points)

            for i in range(num_points):
                field_array.SetValue(i, interpolated_values[i])

            mesh.GetPointData().AddArray(field_array)
            logger.info("Mapped field '%s' to 3D mesh", field_name)

        except Exception as e:
            logger.exception("Failed to map field '%s'", field_name)
            continue

    logger.info("Completed mapping %d fields to 3D mesh loaded from %s", len(fields_to_map), input_vtp_path)

    # Write the mesh with mapped data to output VTP file
    writer = vtkXMLPolyDataWriter()
    writer.SetFileName(str(output_vtp_path))
    writer.SetInputData(mesh)
    writer.Write()

    logger.info("Saved 3D mesh with flow data to %s", output_vtp_path)
    return str(output_vtp_path)
