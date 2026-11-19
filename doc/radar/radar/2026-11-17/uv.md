---
title: UV
ring: trial
quadrant: tools-and-patterns
tags: [python, package manager, performance, saf]
homepage: https://docs.astral.sh/uv/
repository: https://github.com/astral-sh/uv
---

[![](https://img.shields.io/badge/repository-181717?logo=github&logoColor=fff&style=flat)](https://github.com/astral-sh/uv)
[![](https://img.shields.io/badge/documentation-0c7cba?logo=gitbook&logoColor=fff&style=flat)](https://docs.astral.sh/uv/)

**UV** is an extremely fast Python package and project manager written in Rust, developed by Astral (creators of Ruff). UV moves from **hold** to **trial**: work is ongoing to **replace Poetry with UV** across SAF.

## Why UV

- **10-100x faster**: Orders of magnitude faster than pip and Poetry for dependency resolution and installation.
- **Unified tool**: A single tool for package management, virtual environments, and Python version management.
- **Standards-based**: Uses the standard `[project]` table of `pyproject.toml` and a cross-platform `uv.lock` lockfile.

## Current status: Trial

- The SAF monorepo is managed with UV (`uv.lock`), and its tasks run through [Moon](/version/stable/radar/tools-and-patterns/moon/) with `uv run`.
- Lockfiles are checked in CI, and Dependabot keeps UV-managed dependencies up to date.
- Some parts of SAF still rely on Poetry, such as example solutions and solution workflows driven by the SAF CLI. They are being migrated.

## History

In summer 2025, a first attempt to replace Poetry with UV in the **SAF Desktop Installer** was aborted because of compatibility issues between UV and PyInstaller, and UV was put on hold.

## Recommendation

Use UV for new Python projects and packages in the SAF repository. UV moves to **adopt** once the migration from Poetry is complete.
