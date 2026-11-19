---
title: Gitleaks
ring: adopt
quadrant: security-and-compliance
tags: [security, secrets, pre-commit, saf]
homepage: https://gitleaks.io/
repository: https://github.com/gitleaks/gitleaks
---

**Gitleaks** detects potentially hardcoded secrets in source files and Git history.

## How SAF uses Gitleaks

SAF configures Gitleaks as a [pre-commit hook](https://github.com/ansys/saf/blob/main/.pre-commit-config.yaml) and has a root Moon task for scanning history and working-tree files. Repository-specific rules and fixture allowlists are in [`.gitleaks.toml`](https://github.com/ansys/saf/blob/main/.gitleaks.toml).

## Recommendation

Run the repository's pre-commit checks and investigate findings. If a real secret is exposed, follow the applicable incident process and rotate or revoke it; removing it from a file alone is insufficient.
