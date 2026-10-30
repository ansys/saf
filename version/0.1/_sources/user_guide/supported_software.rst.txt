.. _supported_software:


Supported software
##################

SAF integrates with the following Ansys products and third-party tools. Version compatibility
is tracked in the ``versions.json`` file at the root of this repository.

.. list-table:: Supported Ansys Products
   :widths: 30 70
   :header-rows: 1

   * - Product
     - Notes
   * - Ansys Fluent
     - Via PyFluent; requires a valid Ansys license
   * - Ansys Mechanical
     - Via PyMechanical; requires a valid Ansys license
   * - Ansys Electronics Desktop (AEDT)
     - Via PyAEDT; requires a valid Ansys license
   * - Ansys MAPDL
     - Via PyMAPDL; requires a valid Ansys license
   * - Ansys optiSLang
     - Via PyOptiSLang; requires a valid Ansys license
   * - Ansys HPS
     - Via PyHPS; for remote job execution (requires Ansys HPS deployment)
   * - Ansys Minerva
     - For enterprise data management (Ansys customers/Channel Partners only)

.. list-table:: Platform Requirements
   :widths: 30 70
   :header-rows: 1

   * - Requirement
     - Minimum version
   * - Python
     - 3.10
   * - Node.js
     - 18.x (for frontend development)
   * - Docker
     - 24.x (for containerized deployment)
   * - Windows
     - Windows 10 / Windows Server 2019 (for desktop deployment)

.. toctree::
   :maxdepth: 2
   :hidden:
