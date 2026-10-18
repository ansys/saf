Pump
====================================
|python|

.. note::
  This content needs to be configured according to the project specifics.

# Team & Roles

| Role                     |  Owner  |
| ------------------------ | ------- |
| Solution Owner           | XXXXXXX |
| Solution Product Manager | XXXXXXX |
| Domain ``SME``           | XXXXXXX |
| Development Manager      | XXXXXXX |
| Solution developer       | XXXXXXX |
| UI/UX                    | XXXXXXX |
| DevOps                   | XXXXXXX |
| Documentation            | XXXXXXX |

# Prerequisites

| Prerequisite | Description |
|--------------|-------------|
| Operating system | Windows 10 or Ubuntu |
| Python distribution | Python 3.12 |
| Supported Python distributions | Python 3.11, 3.12, 3.13 and 3.14 |
| IDE | [Visual Studio Code](https://code.visualstudio.com/download#) |
| SAF CLI | Install [latest SAF CLI](https://dev-docs.external.solutions.ansys.com/version/stable/getting_started/prerequisites/saf_cli.html) |

# Install the solution

This assumes that SAF CLI is installed and the ``saf`` command is available in the terminal. Therefore, it is not strictly required to run the following commands from any directory in particular.

1. Run the ``saf install`` command with the ``<solution_name>`` argument. By default, it will install ``desktop`` and ``ui`` dependency groups.

```bash
saf install compressor
```

Check the [Install solution’s development environment](https://saf-cli.external.solutions.ansys.com/version/stable/user_guide/install_solution_environment.html) section of the SAF CLI documentation for more options.

# Start the solution

To start the solution run the following command anywhere in the system:

```bash
saf run compressor
```

Check the [Run a solution](https://saf-cli.external.solutions.ansys.com/version/stable/user_guide/run.html) section of the SAF CLI documentation for more options.

# Generate a distributable desktop installer

To generate an executable installer from the solution application:

1. Install the build dependencies:

```bash
saf install compressor -d build
```

2. Run the ``saf build`` command:

```bash
saf build compressor
```

Check the [Build a distributable installer](https://saf-cli.external.solutions.ansys.com/version/stable/user_guide/installer.html) section of the SAF CLI documentation for more options.