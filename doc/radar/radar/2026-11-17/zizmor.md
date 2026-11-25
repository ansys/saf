---
title: zizmor
ring: adopt
quadrant: security-and-compliance
tags: [security, github actions, static analysis, pre-commit, saf]
homepage: https://docs.zizmor.sh/
repository: https://github.com/zizmorcore/zizmor
---

**zizmor** analyzes GitHub Actions workflows for security issues.

## How SAF uses zizmor

SAF runs zizmor in pedantic mode through its [pre-commit configuration](https://github.com/ansys/saf/blob/main/.pre-commit-config.yaml), with an exclusion for the generated solution template.

## Recommendation

Run the repository's pre-commit checks when changing workflows and investigate findings alongside workflow review.
