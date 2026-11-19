---
title: License checks
ring: adopt
quadrant: security-and-compliance
tags: [compliance, licenses, dependencies, saf]
---

**License checks** help identify dependencies or packages with licenses that need review for compliance.

## How SAF checks licenses

Pull-request CI uses the [Ansys license-checking action](https://github.com/ansys/saf/blob/main/.github/workflows/ci_cd_pr.yml) on installed dependencies. The shared Moon `check-license` task builds the package and uses [pip-licenses](https://github.com/raimon49/pip-licenses) to check the package's license against Apache-2.0. Package-specific implementations can differ.

## Recommendation

Run the applicable package's `moon run <package>:check-license` task and review dependency licenses using the CI checks. A package license check alone does not establish compliance for its dependencies.
