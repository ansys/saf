---
title: Dependabot
ring: adopt
quadrant: security-and-compliance
tags: [security, dependencies, vulnerabilities, github, saf]
homepage: https://docs.github.com/en/code-security/dependabot
---

**Dependabot** helps identify vulnerable dependencies and proposes dependency updates through pull requests.

## How SAF uses Dependabot

The [Dependabot configuration](https://github.com/ansys/saf/blob/main/.github/dependabot.yml) covers uv, npm, GitHub Actions, and selected pip projects. SAF's certification workflow also analyzes production Dependabot alerts.

## Recommendation

Review alerts and update pull requests promptly, validate changes, and investigate applicability rather than assuming every alert or update has the same impact.
