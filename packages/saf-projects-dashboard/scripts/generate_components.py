#!/usr/bin/env python
"""
Wrapper script to run dash-generate-components with proper path handling on Windows.

This works around a bug in dash where paths with spaces (like C:\\Program Files\\...)
are not properly quoted when passed to Node.js subprocess.

The fix: Copy extract-meta.js to local directory and use dash.generate_components
with the metadata parameter to bypass the problematic node call.
"""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

RUFF_HEADER = "# ruff: noqa\n"


def _require_dash_or_exit():
    """Fail fast with actionable guidance when dash is not installed."""
    try:
        import dash  # noqa: F401
    except ModuleNotFoundError as exc:
        print(
            "Missing required Python dependency 'dash'.\n"
            "Install it in the active environment, then rerun the build.\n"
            "Examples:\n"
            "  - poetry install --with build\n"
            '  - pip install "dash[dev]>=3.0.0"\n'
            "  - pip install -r scripts/requirements.txt",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc


def _add_license_headers(files):
    """Apply the configured Ansys license-header hook to generated files."""
    command = [
        sys.executable,
        "-m",
        "pre_commit",
        "run",
        "add-license-headers",
        "--files",
        *(str(path.relative_to(Path.cwd())) for path in files),
    ]
    results = []
    for _ in range(2):
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        results.append(result)
        if result.returncode == 0:
            return
    for result in results:
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
    raise subprocess.CalledProcessError(result.returncode, command)


def run_node_extract(components_source, ignore, local_extract_path):
    """Run node extract-meta.js with proper argument handling."""
    # Reserved words from dash — NOTE: we intentionally omit "_.*" here because
    # TypeScript emits internal symbols (e.g. __@iterator@146) that match that
    # pattern and cause extract-meta to fatally error. Instead, we filter out
    # underscore-prefixed props in Python after extraction (see _filter_metadata).
    reserved_words = [
        "UNDEFINED",
        "REQUIRED",
        "to_plotly_json",
        "available_properties",
        "available_wildcard_properties",
    ]
    reserved_patterns = "|".join(f"^{p}$" for p in reserved_words)

    # Set up environment
    env = os.environ.copy()
    env["NODE_PATH"] = "node_modules"
    env["MODULES_PATH"] = str(Path("./node_modules").resolve())

    # Run node with proper argument list (not shell)
    cmd = ["node", str(local_extract_path), ignore or "^_", reserved_patterns, components_source]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        env=env,
    )

    out, err = proc.communicate()
    status = proc.poll()

    if status != 0:
        print(err.decode(), file=sys.stderr)
        return None

    return json.loads(out.decode("utf-8"))


def _filter_metadata(metadata):
    """Remove underscore-prefixed props (TypeScript internals like __@iterator@146)
    from extracted component metadata. This replaces the '_.*' reserved word check
    that was previously done inside extract-meta.js (which treated matches as fatal).
    """
    import re

    for component_data in metadata.values():
        props = component_data.get("props", {})
        keys_to_remove = [k for k in props if re.match(r"^_", k)]
        for key in keys_to_remove:
            del props[key]
    return metadata


def main():
    """Run component generation with Windows path fix."""
    parser = argparse.ArgumentParser(description="Generate Dash component Python wrappers")
    parser.add_argument("components_source", help="Path to TypeScript/React components")
    parser.add_argument("project_shortname", help="Project short name (module name)")
    parser.add_argument(
        "-p", "--package-info", dest="package_info_filename", default="package-info.json", help="Package info JSON file"
    )
    parser.add_argument("-i", "--ignore", default="", help="Regex pattern to ignore files")
    parser.add_argument("-n", "--namespace", default=None, help="Component namespace (defaults to project_shortname)")

    args = parser.parse_args()

    _require_dash_or_exit()

    from importlib.resources import files

    # Get the extract-meta.js script from dash package
    extract_path = str(files("dash").joinpath("extract-meta.js"))

    # Copy to current directory to avoid path with spaces
    local_extract = Path.cwd() / "_extract-meta-local.js"
    shutil.copyfile(extract_path, local_extract)

    try:
        # Generate metadata using our fixed node call
        metadata = run_node_extract(args.components_source, args.ignore, local_extract)

        if metadata is None:
            print(f"Error generating metadata in {args.project_shortname}", file=sys.stderr)
            sys.exit(1)

        # Filter out TypeScript internal symbols (e.g. __@iterator@146) from props
        metadata = _filter_metadata(metadata)

        # Now call dash's generate_components with the metadata already extracted
        from dash.development.component_generator import generate_components

        generate_components(
            args.components_source,
            args.project_shortname,
            package_info_filename=args.package_info_filename,
            ignore=args.ignore,
            metadata=metadata,  # Pass pre-extracted metadata to skip node call
        )

        # Stamp all generated .py files as auto-generated so linters skip them.
        output_dir = Path(args.project_shortname).resolve()
        generated_python_files = []
        for fpath in output_dir.iterdir():
            if fpath.suffix != ".py":
                continue
            generated_python_files.append(fpath)
            with fpath.open(encoding="utf-8") as fh:
                content = fh.read()
            if not content.startswith(RUFF_HEADER):
                with fpath.open("w", encoding="utf-8") as fh:
                    fh.write(RUFF_HEADER + content)

        if args.namespace and args.namespace != args.project_shortname:
            import re

            output_dir = Path(args.project_shortname).resolve()
            for fpath in output_dir.iterdir():
                if fpath.suffix == ".py":
                    with fpath.open(encoding="utf-8") as fh:
                        content = fh.read()
                    patched = re.sub(
                        rf"_namespace\s*=\s*['\"]({re.escape(args.project_shortname)})['\"]",
                        f"_namespace = '{args.namespace}'",
                        content,
                    )
                    if patched != content:
                        with fpath.open("w", encoding="utf-8") as fh:
                            fh.write(patched)
                elif fpath.name == "proptypes.js":
                    # Dash generates proptypes.js using project_shortname as the window key.
                    # Patch it to use the correct namespace so window[namespace] resolves.
                    with fpath.open(encoding="utf-8") as fh:
                        content = fh.read()
                    patched = content.replace(
                        f"window['{args.project_shortname}']",
                        f"window['{args.namespace}']",
                    )
                    if patched != content:
                        with fpath.open("w", encoding="utf-8") as fh:
                            fh.write(patched)
                    else:
                        print(
                            f"Warning: proptypes.js namespace patch found no match for "
                            f"window['{args.project_shortname}']. "
                            "Verify Dash generator output format hasn't changed.",
                            file=sys.stderr,
                        )

        _add_license_headers(generated_python_files)

        print("Component generation complete!")

    finally:
        # Cleanup
        if local_extract.exists():
            local_extract.unlink()


if __name__ == "__main__":
    main()
    