################################################################
Solution Application Framework - Guided Low-Code Workflow Engine
################################################################

|python| |pypi| |GH-CI| |codecov| |Apache| |ruff|

.. |python| image:: https://img.shields.io/pypi/pyversions/ansys-saf-glow-engine?logo=python&logoColor=white&label=Python
   :target: https://pypi.org/project/ansys-saf-glow-engine/
   :alt: Python

.. |pypi| image:: https://img.shields.io/pypi/v/ansys-saf-glow-engine.svg?logo=pypi&logoColor=white&label=PyPI
   :target: https://pypi.org/project/ansys-saf-glow-engine/
   :alt: PyPI

.. |GH-CI| image:: https://img.shields.io/github/actions/workflow/status/ansys/saf/ci_cd_pr.yml?branch=main&label=CI-CD&logo=github
   :target: https://github.com/ansys/saf/actions/workflows/ci_cd_pr.yml?query=branch%3Amain
   :alt: GH-CI

.. |codecov| image:: https://img.shields.io/codecov/c/github/ansys/glow-engine
   :target: https://app.codecov.io/gh/ansys/glow-engine
   :alt: Codecov

.. |Apache| image:: https://img.shields.io/badge/License-Apache2.0-white.svg?labelColor=black
   :target: https://www.apache.org/licenses/
   :alt: Apache

.. |ruff| image:: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
   :target: https://github.com/astral-sh/ruff
   :alt: Ruff


Overview
========

**GLOW Engine** stands for **Guided Low-Code Workflow Engine**. It is the backend
component of the Solution Application Framework (SAF), a modular and extensible
Python framework designed to accelerate the development of simulation-driven
web applications and digital engineering workflows.

GLOW abstracts complex backend operations, orchestrates integrations with Ansys
products, and provides a unified API for building, running, and managing
solution applications. It enables solution developers to focus on business
logic and user experience rather than low-level infrastructure, while taking
advantage of Ansys technologies and best practices for production-ready
engineering applications.

Key capabilities include:

- High-level APIs for defining engineering workflows, transactions, and
  data models without extensive boilerplate code.
- Seamless connectivity with Ansys solvers and tools such as Mechanical,
  Fluent, and MAPDL through PyAnsys SDKs.
- Support for custom steps, plugins, and asset encryption to protect
  intellectual property.
- Designed for both small- and large-scale deployments,
  supporting multi-user, multi-project, and multi-instance scenarios.
- Handles long-running and synchronous transactions with built-in state management,
  error handling, and logging.
- Compatible with Windows 10/11 and Ubuntu 22.04/24.04, and deployable in
  desktop and on-premises environments.

By serving as the backbone of the SAF ecosystem, GLOW Engine allows teams to
deliver powerful, maintainable solution applications more quickly and with
greater consistency.


Installation
============

Ensure you have all the necessary `prerequisites`_.

To install the GLOW Engine, run:

.. code-block:: bash

   pip install ansys-saf-glow-engine


Documentation
=============

Visit the `official documentation`_ for detailed information on how to use the GLOW Engine.
Check the `API reference`_ for a complete list of classes, methods, and usage examples.


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
SAF GLOW Engine. It helps you keep track of updates, bug
fixes, new features, and improvements made to the project over time.

To view the complete changelog, visit the project repository and navigate
to the `CHANGELOG`_ file. It provides a comprehensive list of changes
categorized by version, along with brief descriptions of each change.


.. _official documentation: https://saf.ansys.com/
.. _project repository: https://github.com/ansys/saf/
.. _prerequisites: https://saf.ansys.com/version/stable/getting_started/prerequisites/index.html
.. _API reference: https://saf.ansys.com/version/stable/api/glow-engine/index.html
.. _Contribute: https://saf.ansys.com/version/stable/contribute/index.html
.. _LICENSE: https://github.com/ansys/saf/blob/main/LICENSE
.. _CHANGELOG: https://github.com/ansys/saf/blob/main/packages/glow-engine/CHANGELOG.md
