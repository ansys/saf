# SoupSieve Security Review

**Review date:** 2026-11-14

**Scope:** SoupSieve advisories documented in [dist/soupsieve.md](dist/soupsieve.md), checked against repository manifests, lockfiles, and tracked application source.

## Findings

| # | Severity | File | Lines | Vulnerability | Confidence |
|---|----------|------|-------|---------------|------------|
| 1 | 🟠 HIGH | [dist/soupsieve.md](dist/soupsieve.md) | 9, 11, 13, 15, 17 | GHSA-mmhr-3c5m-f64f — polynomial-time denial of service in descendant-combinator matching; exploitability undetermined | 8/10 |
| 2 | 🟠 HIGH | [dist/soupsieve.md](dist/soupsieve.md) | 10, 12, 14, 16, 18 | GHSA-6655-6qjp-jx7x — exponential selector-compilation regex; exploitability undetermined | 8/10 |
| 3 | 🟡 MEDIUM | [dist/soupsieve.md](dist/soupsieve.md) | 19–23 | GHSA-7g44-g9rc-x53w — uncontrolled selector-parser recursion; exploitability undetermined | 8/10 |

## Assessment

SoupSieve is present transitively through Beautiful Soup in the affected lockfile configurations. The root and SDK `uv.lock` files select SoupSieve 2.10 below Python 3.11.5 and 4.1 starting at Python 3.11.5. The examples and solution-template Poetry lockfiles select 2.10 for Python 3.11 and 4.1 for the later supported Python versions. The template lockfiles place this dependency in the optional `doc` group, not the SAF CLI runtime dependency set.

A tracked-source search found no repository-owned SoupSieve or Beautiful Soup imports/calls and no application path passing HTML or CSS selectors to those libraries. However, that does not establish that transitive dependencies never invoke the vulnerable behavior. The repository also does not establish which extras are installed in deployments, how Jupyter is exposed, or whether untrusted content can reach relevant dependency code.

Consequently, all three findings are **undetermined for product exploitability**: vulnerable dependency versions are present in the stated configurations, but repository and deployment evidence does not establish the attacker-controlled input path required by each advisory. No dynamic exploit test was performed.

## Advisory preconditions

- **GHSA-mmhr-3c5m-f64f:** vulnerable descendant-combinator matching must be reached with deeply nested attacker-influenced HTML or XML.
- **GHSA-6655-6qjp-jx7x:** the vulnerable selector-compilation regex must receive an attacker-supplied selector.
- **GHSA-7g44-g9rc-x53w:** vulnerable selector parsing must receive a deeply nested, attacker-controlled pseudo-class selector.

## Evidence references

- [Root lockfile](uv.lock): SoupSieve 2.10 marker below Python 3.11.5 and 4.1 marker from Python 3.11.5.
- [SDK lockfile](packages/saf-sdk/uv.lock): same Python-version split.
- [Examples lockfile](examples/poetry.lock) and [examples project metadata](examples/pyproject.toml): SoupSieve is in the resolved application dependency set; the project supports Python 3.11 and 3.12.
- [Solution-template Dash lockfile](packages/saf-cli/src/ansys/saf/cli/_solutions/templates/solution/{{cookiecutter.__solution_name}}/lock_files/dash/poetry.lock), [no-UI lockfile](packages/saf-cli/src/ansys/saf/cli/_solutions/templates/solution/{{cookiecutter.__solution_name}}/lock_files/no_ui/poetry.lock), and [template metadata](packages/saf-cli/src/ansys/saf/cli/_solutions/templates/solution/{{cookiecutter.__solution_name}}/pyproject.toml): SoupSieve is part of the optional documentation dependency group.

The confidence score reflects confirmed dependency/version exposure and the absence of repository or deployment evidence establishing the required input paths. It is not a probability that an attack will succeed.
