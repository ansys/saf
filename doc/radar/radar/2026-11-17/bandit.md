---
title: Bandit
ring: adopt
quadrant: security-and-compliance
tags: [security, python, static analysis, saf]
homepage: https://bandit.readthedocs.io/
repository: https://github.com/PyCQA/bandit
---

**Bandit** analyzes Python source code for common security issues.

## How SAF uses Bandit

The [shared Moon task](https://github.com/ansys/saf/blob/main/.moon/tasks/all.yml) scans package source recursively and reports high-severity findings. It is included in the shared package pre-commit task.

## Recommendation

Run `moon run <package>:bandit` for the affected package and review findings alongside other security checks and code review.
