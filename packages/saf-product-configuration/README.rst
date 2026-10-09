######################################################
Solution Application Framework - Product Configuration
######################################################

|python| |pypi| |GH-CI| |codecov| |Apache| |ruff|

.. |python| image:: https://img.shields.io/pypi/pyversions/ansys-saf-product-configuration?logo=python&logoColor=white&label=Python
   :target: https://pypi.org/project/ansys-saf-product-configuration/
   :alt: Python

.. |pypi| image:: https://img.shields.io/pypi/v/ansys-saf-product-configuration.svg?logo=pypi&logoColor=white&label=PyPI
   :target: https://pypi.org/project/ansys-saf-product-configuration/
   :alt: PyPI

.. |GH-CI| image:: https://img.shields.io/github/actions/workflow/status/ansys/saf/ci_cd_pr.yml?branch=main&label=CI-CD&logo=github
   :target: https://github.com/ansys/saf/actions/workflows/ci_cd_pr.yml?query=branch%3Amain
   :alt: GH-CI

.. |codecov| image:: https://img.shields.io/codecov/c/github/ansys/saf-product-configuration
   :target: https://app.codecov.io/gh/ansys/saf-product-configuration
   :alt: Codecov

.. |Apache| image:: https://img.shields.io/badge/License-Apache2.0-white.svg?labelColor=black
   :target: https://www.apache.org/licenses/
   :alt: Apache

.. |ruff| image:: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
   :target: https://github.com/astral-sh/ruff
   :alt: Ruff


Overview
========

SAF Product Configuration provides protocol-based interfaces and ready-to-use product definitions for launching
products in SAF-based solutions.

Out of the box, the package contains the recipes, startup commands, environment settings, and version-specific
metadata needed to launch selected Ansys products in a consistent way through SAF product instance systems such as
HPS and PIM Light. These built-in configurations cover the following products, so solution developers can use proven
launch definitions instead of reimplementing product startup behavior for each deployment.

+------------+------------------------------------------------------------------+
| Product    | Supported versions                                               |
+============+==================================================================+
| MAPDL      | ``2025 R1 SP4``, ``2025 R2 SP4``                                 |
+------------+------------------------------------------------------------------+
| Mechanical | ``2025 R1 SP4``, ``2025 R2 SP4``                                 |
+------------+------------------------------------------------------------------+
| Fluent     | ``2025 R1 SP4``, ``2025 R2 SP4``                                 |
+------------+------------------------------------------------------------------+
| AEDT       | ``2025 R1 SP4``, ``2025 R2 SP4``                                 |
+------------+------------------------------------------------------------------+
| optiSLang  | ``2024 R1``, ``2024 R2``                                         |
+------------+------------------------------------------------------------------+
| Geometry   | Windows ``2025 R1 SP4``, ``2025 R2 SP4``, Linux: ``2025 R2 SP4`` |
+------------+------------------------------------------------------------------+

From a business and solution-development perspective, SAF Product Configuration helps reduce the amount of custom
code that developers need to write and maintain to launch products reliably. It provides an out-of-the-box connector
layer for product startup and lifecycle integration, so teams can focus more on solution logic and user workflows
instead of rebuilding product-specific launch, configuration, and instance-management behavior.

The package is not limited to the built-in Ansys product definitions. It also provides protocol-based interfaces for
describing a product name, supported versions, execution command, environment variables, service type, and transport
settings. This makes it possible for developers to create and load their own custom product configurations to start
additional Ansys products or even third-party applications, while keeping the same SAF integration model and
configuration workflow.


Installation
============

Ensure you have all the necessary `prerequisites`_.

To install SAF Product Configuration, run:

.. code-block:: bash

   pip install ansys-saf-product-configuration


Documentation
=============

Visit the `official documentation`_ for detailed information on how to use SAF Product Configuration.
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
SAF Product Configuration for Python. It helps you keep track of updates, bug
fixes, new features, and improvements made to the project over time.

To view the complete changelog, visit the project repository and navigate
to the `CHANGELOG`_ file. It provides a comprehensive list of changes
categorized by version, along with brief descriptions of each change.


.. _prerequisites: https://saf.ansys.com/version/stable/getting_started/prerequisites/index.html
.. _official documentation: https://saf.ansys.com/
.. _project repository: https://github.com/ansys/saf/
.. _API reference: https://saf.ansys.com/version/stable/api/saf-product-configuration/index.html
.. _Contribute: https://saf.ansys.com/version/stable/contribute/index.html
.. _LICENSE: https://github.com/ansys/saf/blob/main/packages/saf-product-configuration/LICENSE
.. _CHANGELOG: https://github.com/ansys/saf/blob/main/packages/saf-product-configuration/CHANGELOG.md
