---
title: Software Bill of Materials
ring: adopt
quadrant: security-and-compliance
tags: [security, dependencies, supply chain, saf]
homepage: https://www.cisa.gov/sbom
---

A **Software Bill of Materials (SBOM)** inventories software components to support supply-chain visibility and vulnerability management.

## How SAF uses SBOMs

The shared Moon `sbom` task exports a Python package SBOM in CycloneDX format. CI publishes these as artifacts and attaches them to releases. The SAF Solutions Manager extension has its own SBOM task for npm production dependencies.

## Recommendation

Generate and distribute the appropriate SBOM for each release. Use it with vulnerability information and relevant OpenVEX assessments; an inventory alone does not determine exploitability.
