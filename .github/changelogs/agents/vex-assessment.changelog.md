# Changelog: SAF VEX Assessment agent

Changes to the agent definition in
[vex-assessment.agent.md](../../agents/vex-assessment.agent.md). Versions follow
the `Agent version` field in that file and apply to the agent's instructions,
not to the products it assesses.

Use these rules when updating the definition:

- Increase the patch version for clarifications and small additions to
  existing behavior.
- Increase the minor version for new behavior or changed assessment criteria
  or safeguards.
- Increase the major version for changes that make earlier assessments
  non-comparable, such as a new output contract.
- Add an entry in the same change that updates the version.

## [1.0.0] - 2026-11-23

### Added

- Initial agent for auditing SAF OpenVEX documents and assessing Dependabot
  alerts or user-supplied CVE and GHSA identifiers, with a read-only default.
- Workflow: establish scope and inventory, audit existing VEX statements, find
  candidate missing entries, detect conflicting statements, and assess each
  vulnerability per product and configuration.
- Status guidance for `under_investigation`, `affected`, `not_affected` and
  `fixed`, with evidence requirements, and reassessment before releases because
  release workflows rewrite product versions but not assessments.
- Evidence handling: Dependabot retrieval with a token presence check and
  permission-failure handling, release artifact verification through wheel
  `METADATA` and `RECORD` and sdist `PKG-INFO`, and CycloneDX 1.5 SBOM guidance
  (`uv export --all-extras`, `moon run <package>:sbom`, `saf-sdk` meta-package
  workflow, GitHub release assets), including that these SBOMs are
  lock-derived.
- Advisory handling: batch deduplication, session caching, and rate-limit
  (HTTP 429) handling.
- Safeguards: scoped explicit authorization with examples, separate
  authorization for each external or bulk action, branch edits as unapproved
  VEX proposals with verified security-maintainer review through a pull
  request before merge or publication, `SECURITY.md` compliance,
  untrusted-input handling, and defined behavior when the user does not
  respond.
- Require verification of the exact product's runtime dependency closure,
  including selected extras and markers, before creating or editing VEX;
  development/test-only dependencies do not establish product runtime
  exposure.
- Temporary files default to the git-ignored `dist/vex-assessment/` directory.
- Handling of interrupted and resumed assessments, and a limitations section.
- Quick reference commands: token check, alert fetch, proposal generation,
  generator tests, agent definition commit, uncommitted changes,
  SBOM download and regeneration, and creating the temporary directory.
- Output contract per product and configuration, including agent version,
  definition commit, maintainer review, and review date state.
