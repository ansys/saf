---
title: Poetry
ring: hold
quadrant: tools-and-patterns
tags: [poetry]
---

[![](https://img.shields.io/badge/python-ef8d22?logo=hackthebox&logoColor=000&style=flat)](https://www.python.org/)
[![](https://img.shields.io/badge/poetry-60A5FA?logo=poetry&logoColor=fff&style=flat)](https://python-poetry.org/docs/)

Poetry moves from **adopt** to **hold**: work is ongoing to replace Poetry with [UV](/version/stable/radar/tools-and-patterns/uv/) across SAF.

Poetry served SAF well as its dependency management and packaging tool, but UV now offers much faster dependency resolution and installation, and the SAF monorepo is already managed with UV.

Some parts of SAF still rely on Poetry, such as example solutions and solution workflows driven by the SAF CLI. Keep using Poetry where it is still required until those parts are migrated, but do not start new projects with it.
