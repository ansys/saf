---
title: Moon
ring: adopt
quadrant: tools-and-patterns
tags: [build system, task runner, monorepo, ci cd, saf]
homepage: https://moonrepo.dev/moon
repository: https://github.com/moonrepo/moon
---

[![](https://img.shields.io/badge/repository-181717?logo=github&logoColor=fff&style=flat)](https://github.com/moonrepo/moon)
[![](https://img.shields.io/badge/documentation-0c7cba?logo=gitbook&logoColor=fff&style=flat)](https://moonrepo.dev/docs)

**Moon** is a repository management, organization, orchestration, and notification tool written in Rust. Since October 15th, 2026, Moon is the established tooling for **local and remote task execution** in SAF.

## How SAF uses Moon

- **Single entry point**: Building, testing, linting, and documenting the SAF monorepo and its packages all go through `moon run <project>:<task>`, both on developer machines and in GitHub Actions.
- **Toolchain management**: Moon pins and installs the Python, uv, and Node.js versions required by the tasks, so local and CI runs use the same tools.
- **Task graph**: Task dependencies are declared once (for example, the documentation build depends on the technology radar build), and Moon runs them in the right order.
- **Caching and affected runs**: Task inputs and outputs are hashed, so unchanged tasks are skipped. In pull requests, CI only runs the tasks affected by the change (`--affected`).

## Recommendation

Use Moon tasks rather than ad hoc scripts or direct tool invocations when adding or running automation in the SAF repository.
