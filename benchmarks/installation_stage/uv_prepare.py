"""Prepare temporary UV projects and locks inside benchmark payloads."""

from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import tomllib
from typing import Any
from urllib.parse import quote
import zipfile

from prepare import (
    BenchmarkConfig,
    platform_is_windows,
    run_preparation_command,
)


def embedded_python(payload: Path) -> Path:
    """Find the embedded payload interpreter before UV locking."""
    for candidate in (payload / "python" / "python.exe", payload / "python" / "tools" / "python.exe"):
        if candidate.is_file():
            return candidate
    candidate = payload / "python" / "bin" / "python3"
    if candidate.is_file():
        return candidate
    raise RuntimeError(f"Embedded Python interpreter not found in {payload / 'python'}.")


def read_wheel_metadata(wheel: Path) -> tuple[str, str]:
    """Read the canonical package name and version from a wheel."""
    with zipfile.ZipFile(wheel) as archive:
        metadata_files = [
            name
            for name in archive.namelist()
            if name.endswith(".dist-info/METADATA") and name.count("/") == 1
        ]
        if len(metadata_files) != 1:
            raise RuntimeError(f"Expected one METADATA file in {wheel}, found {len(metadata_files)}.")
        metadata = archive.read(metadata_files[0]).decode("utf-8")
    values: dict[str, str] = {}
    for line in metadata.splitlines():
        if ": " in line:
            key, value = line.split(": ", 1)
            if key in {"Name", "Version"}:
                values[key] = value
    if "Name" not in values or "Version" not in values:
        raise RuntimeError(f"Wheel metadata is missing Name or Version: {wheel}")
    return values["Name"], values["Version"]


def canonical_package_name(name: str) -> str:
    """Normalize a package name for a PEP 508 dependency and UV source key."""
    return name.replace("_", "-").replace(".", "-")


def poetry_constraint_to_pep508(value: str) -> str:
    """Convert the Poetry constraints used by the Examples project."""
    value = value.strip()
    if value in {"", "*"}:
        return ""
    parts: list[str] = []
    for raw_part in value.split(","):
        part = raw_part.strip()
        if part.startswith("^"):
            version = part[1:]
            numbers = version.split(".")
            numeric = [int(number) for number in numbers if number.isdigit()]
            if not numeric:
                raise ValueError(f"Unsupported Poetry constraint: {value}")
            while len(numeric) < 3:
                numeric.append(0)
            if numeric[0] > 0:
                upper = (numeric[0] + 1, 0, 0)
            elif numeric[1] > 0:
                upper = (0, numeric[1] + 1, 0)
            else:
                upper = (0, 0, numeric[2] + 1)
            parts.extend([f">={version}", f"<{'.'.join(str(number) for number in upper)}"])
        elif part.startswith("~"):
            version = part.removeprefix("~").strip()
            numbers = [int(number) for number in version.split(".") if number.isdigit()]
            if not numbers:
                raise ValueError(f"Unsupported Poetry constraint: {value}")
            if len(numbers) == 1:
                upper = (numbers[0] + 1, 0)
            else:
                upper = (numbers[0], numbers[1] + 1)
            parts.extend([f">={version}", f"<{'.'.join(str(number) for number in upper)}"])
        elif part.startswith("=") and not part.startswith(("==", ">=", "<=")):
            parts.append(f"=={part.removeprefix('=').strip()}")
        elif not part.startswith((">", "<", "=", "!")):
            parts.append(f"=={part}")
        else:
            parts.append(part)
    return ",".join(parts)


def dependency_requirement(
    name: str,
    value: Any,
    locked_version: str | None = None,
) -> tuple[str, tuple[str, str] | None]:
    """Convert one Poetry dependency to a PEP 508 requirement and source."""
    package_name = canonical_package_name(name)
    if isinstance(value, str):
        constraint = f"=={locked_version}" if locked_version is not None else poetry_constraint_to_pep508(value)
        return f"{package_name}{constraint}", None
    if not isinstance(value, dict):
        raise ValueError(f"Unsupported dependency declaration for {name}: {value!r}")

    extras = value.get("extras", [])
    if not isinstance(extras, list) or not all(isinstance(extra, str) for extra in extras):
        raise ValueError(f"Invalid extras declaration for {name}.")
    suffix = f"[{','.join(extras)}]" if extras else ""
    path = value.get("path")
    if path is not None:
        if not isinstance(path, str):
            raise ValueError(f"Invalid path declaration for {name}.")
        return f"{package_name}{suffix}", (package_name, path)
    version = value.get("version", "")
    if not isinstance(version, str):
        raise ValueError(f"Invalid version declaration for {name}.")
    constraint = f"=={locked_version}" if locked_version is not None else poetry_constraint_to_pep508(version)
    return f"{package_name}{suffix}{constraint}", None


def write_uv_project_from_poetry(project_file: Path, target_environment: str) -> None:
    """Convert the generated Poetry project into a small PEP 621 UV project."""
    original = tomllib.loads(project_file.read_text(encoding="utf-8"))
    poetry = original.get("tool", {}).get("poetry", {})
    dependencies = dict(poetry.get("dependencies", {}))
    for group_name in ("desktop", "ui", "doc"):
        group = poetry.get("group", {}).get(group_name, {})
        group_dependencies = group.get("dependencies", {})
        if isinstance(group_dependencies, dict):
            for name, value in group_dependencies.items():
                dependencies.setdefault(name, value)

    lock_versions: dict[str, str] = {}
    locked_packages: list[dict[str, Any]] = []
    lock_file = project_file.with_name("poetry.lock")
    if lock_file.is_file():
        lock_data = tomllib.loads(lock_file.read_text(encoding="utf-8"))
        for package in lock_data.get("package", []):
            if isinstance(package, dict) and isinstance(package.get("name"), str):
                version = package.get("version")
                if isinstance(version, str):
                    lock_versions.setdefault(canonical_package_name(package["name"]), version)
                    locked_packages.append(package)

    python_requirement = dependencies.pop("python", ">=3.11,<3.13")
    if isinstance(python_requirement, dict):
        python_requirement = python_requirement.get("version", ">=3.11,<3.13")
    if not isinstance(python_requirement, str):
        raise ValueError("The generated Poetry project has an invalid Python requirement.")

    requirements: list[str] = []
    sources: list[tuple[str, str]] = []
    requirement_names: set[str] = set()
    for name, value in sorted(dependencies.items(), key=lambda item: str(item[0]).lower()):
        package_name = canonical_package_name(str(name))
        requirement, source = dependency_requirement(
            str(name),
            value,
            lock_versions.get(package_name),
        )
        requirements.append(requirement)
        requirement_names.add(package_name)
        if source is not None:
            sources.append(source)

    selected_groups = {"main", "desktop", "ui", "doc"}
    for package in locked_packages:
        package_name = canonical_package_name(str(package["name"]))
        groups = package.get("groups", [])
        if isinstance(groups, list) and groups and not selected_groups.intersection(groups):
            continue
        if package_name in requirement_names:
            continue
        requirement = f"{package_name}=={package['version']}"
        marker = package.get("markers")
        if isinstance(marker, str) and marker:
            requirement += f"; {marker}"
        requirements.append(requirement)
        requirement_names.add(package_name)

    project = [
        "[project]",
        'name = "saf-benchmark-project"',
        'version = "0.0.0"',
        f"requires-python = {json.dumps(python_requirement)}",
        "dependencies = [",
        *[f"  {json.dumps(requirement)}," for requirement in requirements],
        "]",
        "",
        "[tool.uv]",
        "package = false",
        f"environments = [{json.dumps(target_environment)}]",
    ]
    if any(isinstance(value, dict) and value.get("allow-prereleases") for value in dependencies.values()):
        project.append('prerelease = "allow"')
    if sources:
        project.extend(["", "[tool.uv.sources]"])
        project.extend(
            f"{json.dumps(name)} = {{ path = {json.dumps(path)} }}"
            for name, path in sources
        )
    project.append("")
    project_file.write_text("\n".join(project), encoding="utf-8")


def write_wheelhouse_project(project_file: Path, wheelhouse: Path, target_environment: str) -> None:
    """Create a minimal UV project whose dependencies come from one wheelhouse."""
    original = tomllib.loads(project_file.read_text(encoding="utf-8"))
    poetry = original.get("tool", {}).get("poetry", {})
    poetry_dependencies = poetry.get("dependencies", {})
    requires_python = poetry_dependencies.get("python", ">=3.11,<3.13")
    if isinstance(requires_python, dict):
        requires_python = requires_python.get("version", ">=3.11,<3.13")
    if not isinstance(requires_python, str):
        raise ValueError("The generated Poetry project has an invalid Python requirement.")

    packages: dict[str, tuple[str, str]] = {}
    for wheel in sorted(wheelhouse.glob("*.whl")):
        name, version = read_wheel_metadata(wheel)
        normalized_name = name.lower().replace("_", "-").replace(".", "-")
        previous = packages.get(normalized_name)
        if previous is not None and previous != (name, version):
            raise RuntimeError(f"Multiple versions of {name} found in {wheelhouse}.")
        packages[normalized_name] = (name, version)

    if not packages:
        raise RuntimeError(f"No wheels found in {wheelhouse}.")
    dependency_lines = [
        f"  {json.dumps(f'{name}=={version}')}"
        for name, version in sorted(packages.values(), key=lambda item: item[0].lower())
    ]
    project = [
        "[project]",
        'name = "saf-benchmark-dependencies"',
        'version = "0.0.0"',
        f"requires-python = {json.dumps(requires_python)}",
        "dependencies = [",
        *[f"{line}," for line in dependency_lines],
        "]",
        "",
        "[tool.uv]",
        "package = false",
        f"environments = [{json.dumps(target_environment)}]",
        "",
    ]
    project_file.write_text("\n".join(project), encoding="utf-8")


def prepare_uv_payload(
    payload: Path,
    metadata_file: Path,
    mode: str,
    variant: str,
    config: BenchmarkConfig,
    preparation_log: Path,
) -> None:
    """Prepare an installed payload for UV and generate its lock file."""
    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    solution_directory = payload / "definitions" / str(metadata["solution-module-name"])
    project_file = solution_directory / "pyproject.toml"
    if not solution_directory.is_dir() or not project_file.is_file():
        raise RuntimeError(f"Invalid UV preparation project: {solution_directory}")
    log_lines: list[str] = [
        "UV preparation uses the Poetry project generated by saf build.",
        "No external migrate-to-uv command is required.",
    ]

    tools_directory = solution_directory / "tools"
    tools_directory.mkdir(parents=True, exist_ok=True)
    uv_target = tools_directory / ("uv.exe" if platform_is_windows() else "uv")
    shutil.copy2(config.uv_executable, uv_target)
    uv_lock = solution_directory / "uv.lock"
    if uv_lock.exists():
        uv_lock.unlink()
    poetry_lock = solution_directory / "poetry.lock"

    wheelhouse = solution_directory / "wheelhouse"
    if variant == "wheelhouse":
        wheelhouse.mkdir(parents=True, exist_ok=True)
        wheels = list(solution_directory.glob("*.whl"))
        if not wheels:
            raise RuntimeError(f"No dependency wheels found for wheelhouse creation in {solution_directory}.")
        for wheel in wheels:
            shutil.copy2(wheel, wheelhouse / wheel.name)
        write_wheelhouse_project(project_file, wheelhouse, config.target_environment)
    else:
        write_uv_project_from_poetry(project_file, config.target_environment)
    if poetry_lock.exists():
        poetry_lock.unlink()

    lock_command: list[str | Path] = [uv_target, "lock", "--python", embedded_python(payload)]
    if mode == "offline":
        lock_command.append("--offline")
    if variant == "wheelhouse":
        lock_command.extend(["--no-index", "--find-links", wheelhouse])
    print(f"{mode}: running 'uv lock'.", flush=True)
    run_preparation_command(lock_command, cwd=solution_directory, output=log_lines)
    preparation_log.write_text("\n\n".join(log_lines) + "\n", encoding="utf-8")


def _poetry_canonical_name(name: str) -> str:
    """Return the PEP 503 normalized package name."""
    return "-".join(
        part
        for part in name.replace("_", "-").replace(".", "-").lower().split("-")
        if part
    )


def _poetry_wheels(solution_directory: Path) -> dict[str, tuple[Path, str]]:
    """Return the dependency wheels bundled in a prepared payload."""
    wheels: dict[str, tuple[Path, str]] = {}
    for wheel in sorted(solution_directory.glob("*.whl")):
        name, version = read_wheel_metadata(wheel)
        key = _poetry_canonical_name(name)
        previous = wheels.get(key)
        if previous is not None and previous[1] != version:
            raise RuntimeError(f"Multiple wheel versions found for {name}.")
        wheels[key] = (wheel, version)
    if not wheels:
        raise RuntimeError(f"No dependency wheels found in {solution_directory}.")
    return wheels


def _replace_poetry_source(text: str, source_block: str | None) -> str:
    """Replace or remove the Poetry package source block."""
    marker = "[[tool.poetry.source]]"
    start = text.find(marker)
    if start < 0:
        raise RuntimeError("The Poetry project does not contain a package source.")
    next_section = text.find("[tool.", start + len(marker))
    if next_section < 0:
        raise RuntimeError("Could not locate the next Poetry tool section.")
    replacement = "" if source_block is None else source_block
    return text[:start] + replacement + text[next_section:]


def _poetry_content_hash(project_file: Path) -> str:
    """Compute Poetry's lock content hash for a rewritten project."""
    project_data = tomllib.loads(project_file.read_text(encoding="utf-8"))
    project_content = project_data.get("project", {})
    group_content = project_data.get("dependency-groups", {})
    tool_poetry_content = project_data.get("tool", {}).get("poetry", {})
    relevant_project_content = {
        key: project_content[key]
        for key in ("requires-python", "dependencies", "optional-dependencies")
        if key in project_content
    }
    relevant_poetry_content: dict[str, Any] = {}
    legacy_keys = {"dependencies", "source", "extras", "dev-dependencies"}
    for key in ("dependencies", "source", "extras", "dev-dependencies", "group"):
        value = tool_poetry_content.get(key)
        if value is None and (
            key not in legacy_keys or relevant_project_content or group_content
        ):
            continue
        relevant_poetry_content[key] = value

    relevant_content: dict[str, Any] = {}
    if relevant_project_content:
        relevant_content["project"] = relevant_project_content
    if group_content:
        relevant_content["dependency-groups"] = group_content
    if relevant_content:
        relevant_content["tool"] = {"poetry": relevant_poetry_content}
    else:
        relevant_content = relevant_poetry_content
    return hashlib.sha256(
        json.dumps(relevant_content, sort_keys=True).encode(),
    ).hexdigest()


def _poetry_dependency_value(
    dependency_name: str,
    declaration: Any,
    wheels: dict[str, tuple[Path, str]],
    variant: str,
) -> str | None:
    """Return a local wheel or server declaration for one Poetry dependency."""
    if dependency_name.lower() == "python":
        return None
    if isinstance(declaration, dict) and "path" in declaration:
        return None
    wheel = wheels.get(_poetry_canonical_name(dependency_name))
    if wheel is None:
        raise RuntimeError(f"No bundled wheel found for Poetry dependency {dependency_name}.")

    wheel_path, version = wheel
    extras = declaration.get("extras", []) if isinstance(declaration, dict) else []
    if not isinstance(extras, list) or not all(isinstance(extra, str) for extra in extras):
        raise RuntimeError(f"Invalid extras for Poetry dependency {dependency_name}.")
    values: list[str]
    if variant == "wheelhouse":
        values = [f'path = "./wheelhouse/{wheel_path.name}"']
    elif variant == "server":
        values = ['version = "' + f"=={version}" + '"', 'source = "offline"']
    else:
        raise ValueError(f"Unsupported Poetry payload variant: {variant}")
    if extras:
        values.append(f"extras = {json.dumps(extras)}")
    return "{ " + ", ".join(values) + " }"


def _poetry_dependency_updates(
    project_data: dict[str, Any],
    wheels: dict[str, tuple[Path, str]],
    variant: str,
) -> dict[str, dict[str, str]]:
    """Build replacements for every Poetry dependency table."""
    poetry = project_data.get("tool", {}).get("poetry", {})
    tables: dict[str, Any] = {
        "tool.poetry.dependencies": poetry.get("dependencies", {}),
    }
    groups = poetry.get("group", {})
    if isinstance(groups, dict):
        for group_name, group in groups.items():
            if isinstance(group, dict):
                tables[f"tool.poetry.group.{group_name}.dependencies"] = group.get(
                    "dependencies",
                    {},
                )

    updates: dict[str, dict[str, str]] = {}
    for table_name, dependencies in tables.items():
        if not isinstance(dependencies, dict):
            continue
        table_updates: dict[str, str] = {}
        for dependency_name, declaration in dependencies.items():
            replacement = _poetry_dependency_value(
                str(dependency_name),
                declaration,
                wheels,
                variant,
            )
            if replacement is not None:
                table_updates[str(dependency_name)] = replacement
        if table_updates:
            updates[table_name] = table_updates
    return updates


def _rewrite_poetry_dependency_tables(
    text: str,
    updates: dict[str, dict[str, str]],
) -> str:
    """Apply dependency replacements while preserving Poetry groups."""
    current_table: str | None = None
    found: dict[str, set[str]] = {name: set() for name in updates}
    rewritten: list[str] = []
    for line in text.splitlines():
        header = re.match(r"^\[([^\]]+)\]\s*$", line)
        if header is not None:
            current_table = header.group(1) if header.group(1) in updates else None
        if current_table is not None:
            match = re.match(r'^\s*(?:"([^"]+)"|([A-Za-z0-9_.-]+))\s*=', line)
            if match is not None:
                dependency_name = match.group(1) or match.group(2)
                replacement = updates[current_table].get(dependency_name)
                if replacement is not None:
                    rewritten.append(f"{dependency_name} = {replacement}")
                    found[current_table].add(dependency_name)
                    continue
        rewritten.append(line)

    missing = {
        table: sorted(set(table_updates) - found[table])
        for table, table_updates in updates.items()
        if set(table_updates) != found[table]
    }
    if missing:
        raise RuntimeError(f"Failed to rewrite Poetry dependencies: {missing}")
    return "\n".join(rewritten) + "\n"


def _write_poetry_simple_index(
    solution_directory: Path,
    wheels: dict[str, tuple[Path, str]],
) -> None:
    """Write a static PEP 503 index for the payload wheelhouse."""
    simple_root = solution_directory / "simple"
    simple_root.mkdir(parents=True, exist_ok=True)
    for package_name, (wheel, _version) in sorted(wheels.items()):
        package_directory = simple_root / package_name
        package_directory.mkdir(parents=True, exist_ok=True)
        link = f"/wheelhouse/{quote(wheel.name)}"
        body = f'<a href="{link}">{html.escape(wheel.name)}</a>\n'
        (package_directory / "index.html").write_text(body, encoding="utf-8")
    index_links = "\n".join(
        f'<a href="{package_name}/">{package_name}</a>'
        for package_name in sorted(wheels)
    )
    (simple_root / "index.html").write_text(index_links + "\n", encoding="utf-8")


def _adapt_poetry_lock(
    lock_file: Path,
    project_file: Path,
    variant: str,
    source_url: str | None,
) -> None:
    """Point file-based Poetry lock sources at the selected offline source."""
    lock_text = lock_file.read_text(encoding="utf-8")
    source_pattern = re.compile(
        r'\[package\.source\]\r?\n'
        r'type = "file"\r?\n'
        r'url = "([^"]+)"\r?\n',
    )

    def replace_source(match: re.Match[str]) -> str:
        if variant == "wheelhouse":
            return (
                "[package.source]\n"
                'type = "file"\n'
                f'url = "wheelhouse/{Path(match.group(1)).name}"\n'
            )
        if source_url is None:
            raise ValueError("A server URL is required for the Poetry server variant.")
        return (
            "[package.source]\n"
            'type = "legacy"\n'
            f'url = "{source_url}"\n'
            'reference = "offline"\n'
        )

    lock_text, source_count = source_pattern.subn(replace_source, lock_text)
    if source_count == 0:
        raise RuntimeError(f"No file package sources found in {lock_file}.")
    lock_text, hash_count = re.subn(
        r'(content-hash\s*=\s*")[^"]+(")',
        rf"\g<1>{_poetry_content_hash(project_file)}\g<2>",
        lock_text,
    )
    if hash_count != 1:
        raise RuntimeError(f"Expected one content hash in {lock_file}, found {hash_count}.")
    lock_file.write_text(lock_text, encoding="utf-8")


def prepare_poetry_payload(
    payload: Path,
    metadata_file: Path,
    variant: str,
    source_url: str | None = None,
) -> str:
    """Prepare a Poetry payload with a local wheelhouse or package server."""
    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    solution_directory = payload / "definitions" / str(metadata["solution-module-name"])
    project_file = solution_directory / "pyproject.toml"
    lock_file = solution_directory / "poetry.lock"
    if not solution_directory.is_dir() or not project_file.is_file() or not lock_file.is_file():
        raise RuntimeError(f"Invalid Poetry preparation project: {solution_directory}")
    wheels = _poetry_wheels(solution_directory)
    wheelhouse = solution_directory / "wheelhouse"
    wheelhouse.mkdir(parents=True, exist_ok=True)
    for wheel, _version in wheels.values():
        shutil.copy2(wheel, wheelhouse / wheel.name)
    readme = solution_directory / "README.md"
    if not readme.exists():
        readme.write_text("Prepared benchmark payload.\n", encoding="utf-8")
    if variant == "server":
        if source_url is None:
            raise ValueError("A server URL is required for the Poetry server variant.")
        _write_poetry_simple_index(solution_directory, wheels)
        source_block = (
            "[[tool.poetry.source]]\n"
            'name = "offline"\n'
            f'url = {json.dumps(source_url)}\n'
            'priority = "primary"\n\n'
        )
    elif variant == "wheelhouse":
        source_block = None
    else:
        raise ValueError(f"Unsupported Poetry payload variant: {variant}")

    project_data = tomllib.loads(project_file.read_text(encoding="utf-8"))
    updates = _poetry_dependency_updates(project_data, wheels, variant)
    project_text = _replace_poetry_source(
        project_file.read_text(encoding="utf-8"),
        source_block,
    )
    project_file.write_text(
        _rewrite_poetry_dependency_tables(project_text, updates),
        encoding="utf-8",
    )
    _adapt_poetry_lock(lock_file, project_file, variant, source_url)
    return (
        f"Poetry payload variant: {variant}\n"
        f"Poetry wheelhouse: {wheelhouse}\n"
        f"Poetry source: {source_url or 'relative wheel paths'}"
    )
