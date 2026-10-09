######################################################
Solution Application Framework - Product Manager
######################################################

|python| |pypi| |GH-CI| |codecov| |Apache| |ruff|

.. |python| image:: https://img.shields.io/pypi/pyversions/ansys-saf-product-manager?logo=python&logoColor=white&label=Python
   :target: https://pypi.org/project/ansys-saf-product-manager/
   :alt: Python

.. |pypi| image:: https://img.shields.io/pypi/v/ansys-saf-product-manager.svg?logo=pypi&logoColor=white&label=PyPI
   :target: https://pypi.org/project/ansys-saf-product-manager/
   :alt: PyPI

.. |GH-CI| image:: https://img.shields.io/github/actions/workflow/status/ansys/saf/ci_cd_pr.yml?branch=main&label=CI-CD&logo=github
   :target: https://github.com/ansys/saf/actions/workflows/ci_cd_pr.yml?query=branch%3Amain
   :alt: GH-CI

.. |codecov| image:: https://img.shields.io/codecov/c/github/ansys/saf?flag=saf-product-manager
   :target: https://app.codecov.io/gh/ansys/saf?flags[0]=saf-product-manager
   :alt: Codecov

.. |Apache| image:: https://img.shields.io/badge/License-Apache2.0-white.svg?labelColor=black
   :target: https://www.apache.org/licenses/
   :alt: Apache

.. |ruff| image:: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
   :target: https://github.com/astral-sh/ruff
   :alt: Ruff


Overview
========

The ``ansys-saf-product-manager`` package provides ready-to-use managers for
launching and controlling Ansys product instances within SAF-based solutions.
Each manager wraps the corresponding PyAnsys client library and exposes a
consistent API for initializing, connecting to, and interacting with the
product.

Within the SAF ecosystem, the Product Manager layer sits between solution code
and the underlying PyAnsys clients. It handles the details of product startup,
connection management, and lifecycle control so that solution developers can
work with Ansys products through a uniform interface without writing low-level
initialization logic themselves.

The package currently supports the following products:

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

Each product manager is packaged as an optional extra, so solutions only pull
in the dependencies they actually need.


Installation
============

Ensure you have all the necessary `prerequisites`_.

To install SAF Product Manager, run:

.. code-block:: bash

   pip install ansys-saf-product-manager


Documentation
=============

Visit the `official documentation`_ for detailed information on how to use SAF Product Manager.
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
SAF Product Manager for Python. It helps you keep track of updates, bug
fixes, new features, and improvements made to the project over time.

To view the complete changelog, please visit the project repository and navigate
to the `CHANGELOG`_ file. It provides a comprehensive list of changes
categorized by version, along with brief descriptions of each change.


.. _prerequisites: https://saf.ansys.com/version/stable/getting_started/prerequisites/index.html
.. _official documentation: https://saf.ansys.com/
.. _project repository: https://github.com/ansys/saf/
.. _API reference: https://saf.ansys.com/version/stable/api/saf-product-manager/index.html
.. _Contribute: https://saf.ansys.com/version/stable/contribute/index.html
.. _LICENSE: https://github.com/ansys/saf/blob/main/packages/saf-product-manager/LICENSE
.. _CHANGELOG: https://github.com/ansys/saf/blob/main/packages/saf-product-manager/CHANGELOG.md