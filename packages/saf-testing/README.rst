######################################################
Solution Application Framework - Testing
######################################################

|python| |pypi| |GH-CI| |codecov| |Apache| |ruff|

.. |python| image:: https://img.shields.io/pypi/pyversions/ansys-saf-testing?logo=python&logoColor=white&label=Python
   :target: https://pypi.org/project/ansys-saf-testing/
   :alt: Python

.. |pypi| image:: https://img.shields.io/pypi/v/ansys-saf-testing.svg?logo=pypi&logoColor=white&label=PyPI
   :target: https://pypi.org/project/ansys-saf-testing/
   :alt: PyPI

.. |GH-CI| image:: https://img.shields.io/github/actions/workflow/status/ansys/saf/ci_cd_pr.yml?branch=main&label=CI-CD&logo=github
   :target: https://github.com/ansys/saf/actions/workflows/ci_cd_pr.yml?query=branch%3Amain
   :alt: GH-CI

.. |codecov| image:: https://img.shields.io/codecov/c/github/ansys/saf-sdk-testing
   :target: https://app.codecov.io/gh/ansys/saf-sdk-testing
   :alt: Codecov

.. |Apache| image:: https://img.shields.io/badge/License-Apache2.0-white.svg?labelColor=black
   :target: https://www.apache.org/licenses/
   :alt: Apache

.. |ruff| image:: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
   :target: https://github.com/astral-sh/ruff
   :alt: Ruff


Overview
========

**SAF SDK Testing** provides a suite of reusable testing utilities, fixtures, and helper methods designed to standardize and streamline testing across the SAF landscape.

This package centralizes testing utilities for SAF-SDK development. It provides a unified testing infrastructure shared across all SAF-SDK repositories, ensuring consistency and reducing duplication in the development of SAF platform components such as the Desktop Orchestrator, Web Portal, Data Management services, and other core modules.

Core Capabilities
-----------------

The package is organized into modular components, each addressing specific testing needs:

- **Common Utilities**: Shared helper functions for general-purpose testing tasks, including network utilities, directory management, and gRPC certificate handling.
- **Database Testing**: Fixtures and methods for testing against PostgreSQL and SQLite databases, including container-managed database instances.
- **Docker Integration**: Tools for managing Docker containers and orchestrating containerized test environments.
- **Frontend/Selenium**: Selenium WebDriver utilities for end-to-end UI testing, including element waiting strategies and browser interaction helpers.
- **HPS Integration**: Testing support for High Performance Computing Services, including deployment processes and stack management.
- **PIM Integration**: Utilities for testing Product Instance Management service interactions.
- **Pytest Enhancements**: Custom pytest fixtures, markers for platform-specific tests, mocking utilities, and test case documentation helpers.
- **E2E Solution Testing**: End-to-end testing infrastructure for SAF solutions, including GLOW engine integration, execution configurations, and project context management.
- **Process Management**: Tools for launching and managing external processes during test execution.

Design Principles
-----------------

This package adheres to strict design principles to ensure reliability and ease of use across the SAF ecosystem:

- **Explicit over implicit**: No ``autouse=True`` fixtures. Developers must explicitly enable fixtures to maintain clarity about test execution.
- **Simplicity and transparency**: Utilities are designed to be easy to understand, allowing developers to predict behavior when calling them.
- **Version-agnostic generality**: Utilities are generic and adaptable, avoiding dependencies on specific versions of SAF components.
- **Flat architecture**: No nested function or fixture calls, maintaining transparency and predictability in test execution.
- **Backward compatibility**: All changes must be backward compatible. Fixes for one repository should never break others.


Installation
============

Ensure you have all the necessary `prerequisites`_.

To install SAF Testing, run:

.. code-block:: bash

   pip install ansys-saf-testing

Getting started
---------------

Add to your package's ``pyproject.toml``:

.. code:: toml

    [tool.poetry.group.tests]
    optional = true
    [tool.poetry.group.tests.dependencies]
    ansys-saf-testing = { version = "^0.1" }
    ...

Pytest fixtures from ``ansys-saf-testing`` are automatically discovered during test collection.
No additional fixture registration or plugin configuration is required.

For methods, just import them when needed. Example:

.. code:: python

    from ansys.saf.testing.selenium import wait_for_element_to_be_clickable, wait_for_partial_text

Extra groups
------------

- ``selenium``: if you want to use Selenium-related fixtures and methods.
- ``hps``: if you want to use fixtures and methods for HPS-related testing.
- ``docker``: if you want to use Docker-related fixtures and methods.
- ``pim``: if you want to use fixtures and methods for PIM light server testing.


Documentation
=============

Visit the `official documentation`_ for detailed information on how to use SAF Testing.


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
SAF SDK Testing for Python. It helps you keep track of updates, bug
fixes, new features, and improvements made to the project over time.

To view the complete changelog, visit the project repository and navigate
to the `CHANGELOG`_ file. It provides a comprehensive list of changes
categorized by version, along with brief descriptions of each change.


.. _official documentation: https://saf.ansys.com/
.. _project repository: https://github.com/ansys/saf/
.. _prerequisites: https://saf.ansys.com/version/stable/getting_started/prerequisites/index.html
.. _Contribute: https://saf.ansys.com/version/stable/contribute/index.html
.. _LICENSE: https://github.com/ansys/saf/blob/main/LICENSE
.. _CHANGELOG: https://github.com/ansys/saf/blob/main/packages/saf-testing/CHANGELOG.md
