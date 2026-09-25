.. _supported_software:


Supported software
##################

Supported software refers to software components that are actively tested in the CI platform and verified to work with the SAF SDK packages. However, the usage of SAF SDK is not limited to these versions, being a python application it's easily portable to other environments.

Python
======

- 3.11, 3.12, 3.13, 3.14

Operating system
================

- Windows: 10, 11, Server 2022
- Ubuntu: 22.04, 24.04

SQLite
======

- 3.37.x, 3.40.x, 3.45.x

PostgreSQL
==========

- 16.0

PIM Light Server
================

- 0.3.12

.. _supported-hps-version:

HPS
===

Used via PyHPS for remote job execution. Requires an Ansys HPS deployment.

- rep-deployments: 1.2.217
- rep-scaling-service: 1.2.217
- rep-evaluator: 1.2.217

Minerva
=======

Used for enterprise data management (Ansys customers and Channel Partners only).

- Minerva: 2025R1
- Ansys Minerva Generic Connector (Minerva CLI): 25.2.202

Ansys flagships
===============

.. list-table:: Supported Ansys products
   :widths: 25 30 45
   :header-rows: 1

   * - Product
     - Supported versions
     - Notes
   * - Ansys Electronics Desktop (AEDT)
     - 2025R1 SP4, 2025R2 SP4
     - Via PyAEDT; requires a valid Ansys license
   * - Ansys Fluent
     - 2025R1 SP4, 2025R2 SP4
     - Via PyFluent; requires a valid Ansys license
   * - Ansys Geometry
     - 2025R1 SP4, 2025R2 SP4
     - Via PyAnsys Geometry; requires a valid Ansys license
   * - Ansys MAPDL
     - 2025R1 SP4, 2025R2 SP4
     - Via PyMAPDL; requires a valid Ansys license
   * - Ansys Mechanical
     - 2025R1 SP4, 2025R2 SP4
     - Via PyMechanical; requires a valid Ansys license
   * - Ansys optiSLang
     - 2024R2, 2025R1 SP4, 2025R2 SP4
     - Via PyOptiSLang; requires a valid Ansys license
   * - Ansys Theia
     - 0.2.5b0
     - For 3D visualization of simulation results

Support for new versions
------------------------

Whenever a new version of Ansys products is released, it will be added as soon as possible. However, solutions requiring support for a new version must wait
until the new version is properly integrated, tested, and SAF packages are released.
Once the support for the new version has been finalized, solutions will need to upgrade their dependency to align with the updated version.

SAF certification always runs against the latest two supported versions of Ansys products.
This ensures that SAF consistently operates with the most up-to-date versions and verifies that the most recent versions are fully functional.

Support for older Ansys product versions
----------------------------------------

You can enable support for older Ansys product versions by following the guidelines for modifying the built-in product managers and configurations. See :ref:`this section <instance_management_modify_builtin_products>` for more details. Note that the responsibility of ensuring that they work properly is on the solution itself.

Additional development tooling
==============================

.. list-table:: Development and deployment tooling
   :widths: 30 70
   :header-rows: 1

   * - Requirement
     - Minimum version
   * - Node.js
     - 18.x (for frontend development)
   * - Docker
     - 24.x (for containerized deployment)

.. toctree::
   :maxdepth: 2
   :hidden:
