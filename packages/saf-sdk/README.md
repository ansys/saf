# Solution Application Framework - SDK

**ansys-saf-sdk** is a meta-package that bundles the core SAF packages into a single, versioned package. It has no code of its own — it only declares dependencies on the individual SAF packages, pinned to their latest compatible versions.

**Note:** Installing `ansys-saf-sdk` requires **pip 26.0** or higher.

## Core dependencies

Installing `ansys-saf-sdk` installs these packages by default:

- `ansys-bdm-api`
- `ansys-bdm-shared-volume`
- `ansys-saf-glow-engine`
- `ansys-iam-oidc`
- `ansys-saf-product-configuration`
- `ansys-saf-product-manager`

## Extras

Optional extras pull in additional packages, or extras of the core packages, for specific scenarios:

| Extra                            | Description                                                                                 |
| -------------------------------- | ------------------------------------------------------------------------------------------- |
| `core-dash`                      | GLOW engine support for Dash-based frontends.                                               |
| `core-pim`                       | GLOW engine support for Product Instance Management (PIM).                                  |
| `core-hps`                       | GLOW engine support for HPC Platform Services (HPS).                                        |
| `core-test`                      | GLOW engine testing utilities.                                                              |
| `core-mcp`                       | GLOW engine support for the Model Context Protocol (MCP).                                   |
| `core-all`                       | All optional extras of the core packages.                                                   |
| `instance-management`            | Product configuration and product manager packages.                                         |
| `instance-management-fluent`     | Instance management support for Ansys Fluent.                                               |
| `instance-management-aedt`       | Instance management support for Ansys Electronics Desktop (AEDT).                           |
| `instance-management-optislang`  | Instance management support for optiSLang.                                                  |
| `instance-management-geometry`   | Instance management support for Ansys Geometry.                                             |
| `instance-management-mapdl`      | Instance management support for Ansys MAPDL.                                                |
| `instance-management-mechanical` | Instance management support for Ansys Mechanical.                                           |
| `instance-management-visor`      | Instance management support for Visor-based products.                                       |
| `instance-management-all`        | All instance management product integrations.                                               |
| `desktop`                        | Desktop orchestrator, Projects dashboard for running solution applications as desktop apps. |
| `ui`                             | UI Projects Dashboard for managing projects instances within a solution.                    |
| `build`                          | Desktop installer, for building standalone desktop installers.                              |
| `all`                            | Every optional extra combined.                                                              |
