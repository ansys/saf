#####################################################
Solution Application Framework - CLI
#####################################################

|python| |pypi| |GH-CI| |codecov| |Apache| |ruff|

.. |python| image:: https://img.shields.io/pypi/pyversions/ansys-saf-cli?logo=python&logoColor=white&label=Python
   :target: https://pypi.org/project/ansys-saf-cli/
   :alt: Python

.. |pypi| image:: https://img.shields.io/pypi/v/ansys-saf-cli.svg?logo=pypi&logoColor=white&label=PyPI
   :target: https://pypi.org/project/ansys-saf-cli/
   :alt: PyPI

.. |GH-CI| image:: https://img.shields.io/github/actions/workflow/status/ansys/saf/ci_cd_pr.yml?branch=main&label=CI-CD&logo=github
   :target: https://github.com/ansys/saf/actions/workflows/ci_cd_pr.yml?query=branch%3Amain
   :alt: GH-CI

.. |codecov| image:: https://img.shields.io/codecov/c/github/ansys/saf-cli
   :target: https://app.codecov.io/gh/ansys/saf-cli
   :alt: Codecov

.. |Apache| image:: https://img.shields.io/badge/License-Apache2.0-white.svg?labelColor=black
   :target: https://www.apache.org/licenses/
   :alt: Apache

.. |ruff| image:: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
   :target: https://github.com/astral-sh/ruff
   :alt: Ruff


Overview
========

SAF CLI is a command-line tool that streamlines the development, management, and packaging of SAF-based solutions.
It provides a unified developer workflow for common SAF tasks such as scaffolding new solutions, installing and
managing solution environments, running solutions locally, executing commands in the correct Python environment,
building distributable installers, archiving solution source code, and listing registered solutions. Under the hood,
it helps coordinate the tools and services involved in the SAF ecosystem so that developers can work with solutions
through a consistent command set instead of stitching together manual steps.

+------------+------------------------------------------------------------------+
| Command    | Description                                                      |
+============+==================================================================+
| new        | Scaffold a new SAF solution from a template.                     |
+------------+------------------------------------------------------------------+
| install    | Set up the solution development environment and dependencies.    |
+------------+------------------------------------------------------------------+
| run        | Run a solution locally for development and testing.              |
+------------+------------------------------------------------------------------+
| execute    | Run arbitrary commands in the solution Python environment.       |
+------------+------------------------------------------------------------------+
| build      | Build a distributable package or installer for a solution.       |
+------------+------------------------------------------------------------------+
| add-step   | Add a new step to an existing SAF solution.                      |
+------------+------------------------------------------------------------------+
| archive    | Archive a solution source tree into a distributable bundle.      |
+------------+------------------------------------------------------------------+
| solutions  | List the solutions registered in the SAF solution database.      |
+------------+------------------------------------------------------------------+
| doc        | Open the SAF CLI documentation.                                  |
+------------+------------------------------------------------------------------+

The CLI is designed to improve developer productivity and solution consistency across the full solution lifecycle.
It reduces setup friction for new projects, lowers the amount of custom scripting teams need to maintain, and makes
local development, packaging, and delivery more repeatable.


Installation
============

Ensure you have all the necessary `prerequisites`_.

To install SAF CLI, run:

.. code-block:: bash

   pip install ansys-saf-cli


Documentation
=============

Visit the `official documentation`_ for detailed information on how to use SAF CLI.


Troubleshooting
===============

For troubleshooting or reporting issues, please open an issue in the `project repository`_.

Please follow these steps to report an issue:

- Go to the project repository.
- Click on the ``Issues`` tab.
- Click on the ``New Issue`` button.
- Provide a clear and detailed description of the issue you are facing.
- Include any relevant error messages, code snippets, or screenshots.

Additionally, you can refer to the `official documentation`_ for additional
resources and troubleshooting guides.


Contribute
==========

Contributions are welcome!
If you would like to contribute, please follow the guidelines provided in the `Contribute`_
section of the official documentation.


License
=======

You can find the full text of the license in the `LICENSE`_ file.


Changelog
=========

The changelog section provides a summary of notable changes for each version of
SAF CLI for Python. It helps you keep track of updates, bug
fixes, new features, and improvements made to the project over time.

To view the complete changelog, visit the project repository and navigate
to the `CHANGELOG`_ file. It provides a comprehensive list of changes
categorized by version, along with brief descriptions of each change.


.. _official documentation: https://saf.ansys.com/
.. _project repository: https://github.com/ansys/saf/
.. _prerequisites: https://saf.ansys.com/version/stable/getting_started/prerequisites/index.html
.. _Contribute: https://saf.ansys.com/version/stable/contribute/index.html
.. _LICENSE: https://github.com/ansys/saf/blob/main/packages/saf-cli/LICENSE
.. _CHANGELOG: https://github.com/ansys/saf/blob/main/packages/saf-cli/CHANGELOG.md
