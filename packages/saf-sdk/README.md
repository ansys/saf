# Solution Application Framework - SDK

[![Python](https://img.shields.io/pypi/pyversions/ansys-saf-sdk?logo=python&logoColor=white&label=Python)](https://pypi.org/project/ansys-saf-sdk/)
[![PyPI](https://img.shields.io/pypi/v/ansys-saf-sdk.svg?logo=pypi&logoColor=white&label=PyPI)](https://pypi.org/project/ansys-saf-sdk/)
[![GH-CI](https://img.shields.io/github/actions/workflow/status/ansys/saf/ci_cd_pr.yml?branch=main&label=CI-CD&logo=github)](https://github.com/ansys/saf/actions/workflows/ci_cd_pr.yml?query=branch%3Amain)
[![Apache](https://img.shields.io/badge/License-Apache2.0-white.svg?labelColor=black)](https://www.apache.org/licenses/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

## Overview

**ansys-saf-sdk** is a meta-package that bundles the core SAF packages into a single, versioned package. It has no code of its own — it only declares dependencies on the individual SAF packages, pinned to their latest compatible versions.

## Installation

Ensure you have all the necessary [prerequisites](https://saf.ansys.com/version/stable/getting_started/prerequisites/index.html).

**Note:** Installing `ansys-saf-sdk` requires **pip 26.0** or higher.

To install the SAF SDK, run:

```bash
pip install ansys-saf-sdk
```

### Core dependencies

Installing `ansys-saf-sdk` installs these packages by default:

- `ansys-bdm-api`
- `ansys-bdm-shared-volume`
- `ansys-saf-glow-engine`
- `ansys-iam-oidc`
- `ansys-saf-product-configuration`
- `ansys-saf-product-manager`

### Extras

Optional extras pull in additional packages, or extras of the core packages, for specific scenarios:

| Extra | Description |
| --- | --- |
| `core-dash` | GLOW engine support for Dash-based frontends. |
| `core-pim` | GLOW engine support for Product Instance Management (PIM). |
| `core-hps` | GLOW engine support for HPC Platform Services (HPS). |
| `core-test` | GLOW engine testing utilities. |
| `core-mcp` | GLOW engine support for the Model Context Protocol (MCP). |
| `core-all` | All optional extras of the core packages. |
| `instance-management` | Product configuration and product manager packages. |
| `instance-management-fluent` | Instance management support for Ansys Fluent. |
| `instance-management-aedt` | Instance management support for Ansys Electronics Desktop (AEDT). |
| `instance-management-optislang` | Instance management support for optiSLang. |
| `instance-management-geometry` | Instance management support for Ansys Geometry. |
| `instance-management-mapdl` | Instance management support for Ansys MAPDL. |
| `instance-management-mechanical` | Instance management support for Ansys Mechanical. |
| `instance-management-visor` | Instance management support for Visor-based products. |
| `instance-management-all` | All instance management product integrations. |
| `desktop` | Desktop orchestrator, for running solution applications as desktop apps. |
| `build` | Desktop installer, for building standalone desktop installers. |
| `all` | Every optional extra combined. |

For example, to install the SAF SDK with Dash and PIM support:

```bash
pip install "ansys-saf-sdk[core-dash,core-pim]"
```

## Documentation

Visit the [official documentation](https://saf.ansys.com/) for detailed information on how to use the SAF SDK.

## Troubleshooting

For troubleshooting or reporting issues, please open an issue in the [project repository](https://github.com/ansys/saf/).

Please follow these steps to report an issue:

- Go to the project repository.
- Click on the `Issues` tab.
- Click on the `New Issue` button.
- Provide a clear and detailed description of the issue you are facing.
- Include any relevant error messages, code snippets, or screenshots.

Additionally, you can refer to the [official documentation](https://saf.ansys.com/) for additional
resources and troubleshooting guides.

## Contribute

Contributions are welcome!
If you would like to contribute, please follow the guidelines provided in the [Contribute](https://saf.ansys.com/version/stable/contribute/index.html)
section of the official documentation.

## License

You can find the full text of the license in the [LICENSE](https://github.com/ansys/saf/blob/main/packages/saf-sdk/LICENSE) file.

## Changelog

The changelog section provides a summary of notable changes for each version of
the SAF SDK. It helps you keep track of updates, bug
fixes, new features, and improvements made to the project over time.

This package has no code of its own, so it has no changelog file. Each bundled package maintains its own
`CHANGELOG.md` in the [packages](https://github.com/ansys/saf/tree/main/packages) directory of the project repository.
