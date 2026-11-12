# update_lock_files.py

A utility script to batch-update dependency lock files (`poetry.lock`, `uv.lock`, and optionally `package-lock.json`) across a repository.

## Overview

This script recursively searches for Poetry, uv, and npm project directories and updates specified packages in their lock files. It's useful for propagating dependency updates across monorepos or multi-project repositories.

## Usage

```bash
uv run scripts/update_lock_files.py <packages> [--root-dir <path>] [--one-by-one] [--npm]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `packages` | **Required.** Comma-separated list of packages to update (e.g., `ansys-saf-glow,ansys-saf-cli`) |
| `--root-dir` | Optional. Root directory to search for lock files. Defaults to the repository root. |
| `--one-by-one` | Optional. Update packages individually instead of all at once. Useful when not all packages exist in every project. |
| `--npm` | Optional. Update npm `package-lock.json` files instead of Python lock files. |

### Examples

Update a single package across all projects:

```bash
uv run scripts/update_lock_files.py requests
```

Update multiple packages:

```bash
uv run scripts/update_lock_files.py "ansys-saf-glow,ansys-saf-cli,requests"
```

Update packages one by one (continues if a package is missing from a project):

```bash
uv run scripts/update_lock_files.py "ansys-saf-glow,ansys-saf-cli" --one-by-one
```

Update npm packages instead of Python packages:

```bash
uv run scripts/update_lock_files.py "lodash,express" --npm
```

Search from a specific directory:

```bash
uv run scripts/update_lock_files.py requests --root-dir ./packages
```

## Behavior

### Python mode (default)

1. **Discovery**: Recursively walks the directory tree to find all `poetry.lock` and `uv.lock` files
2. **Poetry projects**: Runs `poetry update <packages> --lock` in each directory
3. **uv projects**: Runs `uv lock --upgrade-package <package>` for each package in each directory

### npm mode (`--npm`)

1. **Discovery**: Recursively walks the directory tree to find all `package-lock.json` files
2. **npm projects**: Runs `npm update <packages>` in each directory

### Error handling

If an update fails (e.g., package not found), the script prints a warning with the error details and continues to the next lock file.

### Report

After completion, the script generates a markdown report at `dist/lock_update_report.md` containing:

- **Summary**: Counts of updated, unchanged, not found, and errored packages
- **Details**: Per-lock-file table showing each package's version before and after the update

Example report output:

```markdown
# Lock File Update Report

**Generated:** 2026-11-02 14:30:00 UTC
**Packages:** requests, flask

## Summary

- **Updated:** 3
- **Unchanged:** 1
- **Not found:** 2
- **Errors:** 0

## Details

### project1/poetry.lock

| Package | Before | After | Status |
|---------|--------|-------|--------|
| requests | 2.28.0 | 2.31.0 | updated |
| flask | 2.3.0 | 2.3.0 | unchanged |
```

### Update Modes

- **Default (all at once)**: Updates all specified packages in a single command. Faster, but fails the entire update for a project if any package is missing.
- **`--one-by-one`**: Updates each package separately. Slower, but allows partial success when some packages don't exist in a project.

### Excluded Directories

The script skips common non-project directories to improve performance:

- Version control: `.git`, `.hg`, `.svn`
- Python caches: `__pycache__`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`
- Virtual environments: `.venv`, `venv`, `.nox`, `.tox`
- Build artifacts: `build`, `dist`, `node_modules`
- Templates: `{{cookiecutter.__solution_name}}`

## Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (for uv projects and running Poetry via uvx)
- [npm](https://www.npmjs.com/) (for npm projects, only required with `--npm`)

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success (warnings may have been printed for individual failures) |

## License

Apache License 2.0 - See the script header for full license text.
