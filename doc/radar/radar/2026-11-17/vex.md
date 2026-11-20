---
title: OpenVEX
ring: adopt
quadrant: security-and-compliance
tags: [security, vulnerabilities, supply chain, saf]
homepage: https://openvex.dev/
repository: https://github.com/openvex/spec
---

**OpenVEX** provides a format for recording whether and how a vulnerability affects a product. It complements an SBOM, which inventories components but does not itself assess their exploitability.

## How SAF uses OpenVEX

Package assessments are stored in the [VEX directory](https://github.com/ansys/saf/tree/main/VEX). The [VEX generator](https://github.com/ansys/saf/blob/main/scripts/generate_vex.py) creates or updates these documents, and release workflows attach a package's VEX document when one is present.

## Recommendation

Document evidence-based vulnerability assessments and reassess statements for each release; changing a product version does not establish that an earlier assessment remains valid.
