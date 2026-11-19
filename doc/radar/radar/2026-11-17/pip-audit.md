---
title: pip-audit
ring: adopt
quadrant: security-and-compliance
tags: [security, python, dependencies, vulnerabilities, saf]
homepage: https://pypi.org/project/pip-audit/
repository: https://github.com/pypa/pip-audit
---

**pip-audit** checks Python dependencies for known vulnerabilities. SAF's shared Moon `vulnerability-check` task audits exported production requirements and writes a Markdown report.

## How SAF uses pip-audit

Pull-request CI audits affected packages, and certification runs the check for the package being certified. The task is defined in the [shared Moon tasks](https://github.com/ansys/saf/blob/main/.moon/tasks/all.yml).

## Recommendation

Run the relevant package's `moon run <package>:vulnerability-check` task and investigate reported vulnerabilities. A clean audit does not guarantee that dependencies are free of unknown vulnerabilities.
