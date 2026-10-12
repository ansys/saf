#####################################################
Solution Application Framework - Desktop Orchestrator
#####################################################

|python| |pypi| |GH-CI| |codecov| |Apache| |ruff|

.. |python| image:: https://img.shields.io/pypi/pyversions/ansys-saf-desktop-orchestrator?logo=python&logoColor=white&label=Python
   :target: https://pypi.org/project/ansys-saf-desktop-orchestrator/
   :alt: Python

.. |pypi| image:: https://img.shields.io/pypi/v/ansys-saf-desktop-orchestrator.svg?logo=pypi&logoColor=white&label=PyPI
   :target: https://pypi.org/project/ansys-saf-desktop-orchestrator/
   :alt: PyPI

.. |GH-CI| image:: https://img.shields.io/github/actions/workflow/status/ansys/saf/ci_cd_pr.yml?branch=main&label=CI-CD&logo=github
   :target: https://github.com/ansys/saf/actions/workflows/ci_cd_pr.yml?query=branch%3Amain
   :alt: GH-CI

.. |codecov| image:: https://img.shields.io/codecov/c/github/ansys/saf?flag=saf-desktop-orchestrator
   :target: https://app.codecov.io/gh/ansys/saf?flags[0]=saf-desktop-orchestrator
   :alt: Codecov

.. |Apache| image:: https://img.shields.io/badge/License-Apache2.0-white.svg?labelColor=black
   :target: https://www.apache.org/licenses/
   :alt: Apache

.. |ruff| image:: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
   :target: https://github.com/astral-sh/ruff
   :alt: Ruff


Overview
========

The **SAF Desktop Orchestrator** is the central controller for running
SAF-based solutions in standalone desktop environments. It is responsible for
starting, health-checking, and shutting down all the services that a solution
needs to run on a user's local machine.

When a solution is launched, the orchestrator coordinates the startup of the
following components in a controlled sequence:

- **Solution API**: The backend service derived from the solution that exposes
  project data and transaction methods.
- **Solution UI**: The front-end displayed in a native window (via pywebview)
  or in an external browser.
- **Portal**: A UI for creating and managing projects within a solution.
- **OTEL Dashboard**: A web dashboard for viewing logs and traces from the
  various services.
- **PIM Light Server**: A lightweight server that creates product instances in
  isolated environments, separate from the method execution environment.
- **Additional services**: Other stateless or custom services defined by the
  solution.

The orchestrator also manages health checks to ensure each service is ready
before the solution UI is displayed, and it handles graceful shutdown when the
user closes the application.

.. note::

   The **Portal**, **OTEL Dashboard**, and **PIM Light Server** are not
   open-source components. For more information about these capabilities,
   contact the PyAnsys core team at pyansys-core@synopsys.com.


Installation
============

Ensure you have all the necessary `prerequisites`_.

To install SAF Desktop Orchestrator, run:

.. code-block:: bash

   pip install ansys-saf-desktop-orchestrator


Documentation
=============

Visit the `official documentation`_ for detailed information on how to use SAF Desktop Orchestrator.


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
SAF Desktop Orchestrator for Python. It helps you keep track of updates, bug
fixes, new features, and improvements made to the project over time.

To view the complete changelog, visit the project repository and navigate
to the `CHANGELOG`_ file. It provides a comprehensive list of changes
categorized by version, along with brief descriptions of each change.


.. _official documentation: https://saf.ansys.com/
.. _project repository: https://github.com/ansys/saf/
.. _prerequisites: https://saf.ansys.com/version/stable/getting_started/prerequisites/index.html
.. _Contribute: https://saf.ansys.com/version/stable/contribute/index.html
.. _LICENSE: https://github.com/ansys/saf/blob/main/packages/saf-desktop-orchestrator/LICENSE
.. _CHANGELOG: https://github.com/ansys/saf/blob/main/packages/saf-desktop-orchestrator/CHANGELOG.md
