---
title: UV
ring: hold
quadrant: tools-and-patterns
tags: [python, package manager, performance, saf]
homepage: https://docs.astral.sh/uv/
repository: https://github.com/astral-sh/uv
---
[![](https://img.shields.io/badge/repository-181717?logo=github&logoColor=fff&style=flat)](https://github.com/astral-sh/uv)
[![](https://img.shields.io/badge/documentation-0c7cba?logo=gitbook&logoColor=fff&style=flat)](https://docs.astral.sh/uv/)

**UV** is an extremely fast Python package and project manager written in Rust, developed by Astral (creators of Ruff). While highly promising for its exceptional performance, UV is currently on **hold** in SAF due to compatibility issues encountered during migration efforts.

## Performance Promise

UV offers significant advantages that make it attractive for SAF:

- **10-100x Faster**: Orders of magnitude faster than pip and Poetry for dependency resolution and installation
- **Unified Tool**: Single tool for package management, virtual environments, and Python version management
- **Rust-Powered**: Built in Rust for maximum performance and reliability
- **pip-Compatible**: Drop-in replacement for pip with familiar commands

## Migration Attempt: Summer 2025

During summer 2025, the SAF team attempted to replace Poetry with UV in the **SAF Desktop Installer**:

- **Goal**: Leverage UV's performance benefits to speed up installer build times
- **Blocker**: Multiple compatibility issues and conflicts between UV and PyInstaller emerged
- **Status**: Migration effort was aborted due to these technical challenges

## Current Status: Hold

UV remains on **hold** while Poetry continues as the standard dependency management tool for SAF projects. The hold status reflects:

- Recognition of UV's potential but acknowledgment of current incompatibilities
- Need for ecosystem maturity and better PyInstaller integration

## Mid-Term Vision

Despite the current hold, the **long-term strategy is to replace Poetry with UV across all SAF components** once:

- PyInstaller compatibility issues are resolved (either by UV, PyInstaller, or the SAF team)
- UV reaches sufficient maturity for production use in complex packaging scenarios
