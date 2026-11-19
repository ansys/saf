---
title: CodeQL
ring: adopt
quadrant: security-and-compliance
tags: [security, static analysis, github, saf]
homepage: https://codeql.github.com/
repository: https://github.com/github/codeql
---

**CodeQL** performs semantic code analysis to identify potential security vulnerabilities and errors.

## How SAF uses CodeQL

The [CodeQL workflow](https://github.com/ansys/saf/blob/main/.github/workflows/codeql.yml) analyzes Python and JavaScript/TypeScript. It runs on a schedule, can be triggered manually, and is called by pull-request CI.

## Recommendation

Review and triage CodeQL findings in addition to using package-level checks and code review. Static analysis cannot establish that code is free of vulnerabilities.
