.. _instance_management_supported_products:

Supported product instance managers
###################################

Overview
========

By default, SAF GLOW Engine  includes product instance managers for the following products:

.. raw:: html

   <table class="pim-summary-table">
     <thead>
       <tr>
         <th>Product</th>
         <th>Supported versions</th>
         <th>Manager classes</th>
         <th>PyAnsys SDK</th>
         <th>Secure transport modes</th>
       </tr>
     </thead>
     <tbody>
       <tr>
         <td><strong>AEDT</strong></td>
         <td>
           <span class="pim-badge">2025 R1 SP4</span>
           <span class="pim-badge">2025 R2 SP4</span>
         </td>
         <td>
           <code>HfssManager</code><br>
           <code>IcepakManager</code><br>
           <code>Maxwell2DManager</code><br>
           <code>Maxwell3DManager</code>
         </td>
         <td><code>pyaedt</code> <span class="pim-badge">1.0.1</span></td>
         <td><span class="pim-secure-yes">WNUA, UDS, mTLS, insecure</span></td>
       </tr>
       <tr>
         <td><strong>Fluent</strong></td>
         <td>
           <span class="pim-badge">2025 R1 SP4</span>
           <span class="pim-badge">2025 R2 SP4</span>
         </td>
         <td>
           <code>Fluent3DDPSolverSecureManager</code><br>
           <code>Fluent2DDPSolverSecureManager</code><br>
           <code>Fluent3DDPMeshingSecureManager</code>
         </td>
         <td><code>ansys-fluent-core</code> <span class="pim-badge">0.37.0</span></td>
         <td><span class="pim-secure-yes">WNUA, UDS, mTLS, insecure</span></td>
       </tr>
       <tr>
         <td><strong>Geometry</strong></td>
         <td>
           <span class="pim-badge">2025 R1 SP4</span>
           <span class="pim-badge">2025 R2 SP4</span>
         </td>
         <td><code>GeometrySecureManager</code></td>
         <td><code>ansys-geometry-core</code> <span class="pim-badge">0.14.2</span></td>
         <td><span class="pim-secure-yes">WNUA, UDS, mTLS, insecure</span></td>
       </tr>
       <tr>
         <td><strong>MAPDL</strong></td>
         <td>
           <span class="pim-badge">2025 R1 SP4</span>
           <span class="pim-badge">2025 R2 SP4</span>
         </td>
         <td><code>MapdlSecureManager</code></td>
         <td><code>ansys-mapdl-core</code> <span class="pim-badge">0.73.0</span></td>
         <td><span class="pim-secure-yes">WNUA, UDS, mTLS, insecure</span></td>
       </tr>
       <tr>
         <td><strong>Mechanical</strong></td>
         <td>
           <span class="pim-badge">2025 R1 SP4</span>
           <span class="pim-badge">2025 R2 SP4</span>
         </td>
         <td><code>MechanicalSecureManager</code></td>
         <td><code>ansys-mechanical-core</code> <span class="pim-badge">0.12.0</span></td>
         <td><span class="pim-secure-yes">WNUA, mTLS, insecure</span></td>
       </tr>
       <tr>
         <td><strong>optiSLang</strong></td>
         <td>
           <span class="pim-badge">2024 R1</span>
           <span class="pim-badge">2024 R2</span>
         </td>
         <td><code>OptislangManager</code></td>
         <td><code>ansys-optislang-core</code> <span class="pim-badge">0.9.4</span></td>
         <td><span class="pim-secure-na">N/A (insecure only)</span></td>
       </tr>
       <tr>
         <td><strong>Visor</strong></td>
         <td>
           <span class="pim-badge">0</span>
         </td>
         <td><code>VisorManager</code></td>
         <td><code>ansys-visor-viewer</code> <span class="pim-badge">0.2.5b0</span></td>
         <td><span class="pim-secure-na">N/A (insecure only)</span></td>
       </tr>
     </tbody>
   </table>

.. important::

    gRPC secure transport is available only for product instance managers and configurations that explicitly state secure support (for example, ``GeometrySecureManager``).
    Product instance managers that are not explicitly marked as secure STILL BYPASS the requirements when interacting with the product instances, relying on insecure connections affected by the gRPC vulnerabilities recently disclosed by Ansys.


Ansys Electronics Desktop
===========================

- ``HfssManager``
- ``IcepakManager``
- ``Maxwell2DManager``
- ``Maxwell3DManager``

To be imported from ``ansys.saf.product_manager.aedt``.

Supported versions
------------------

- AEDT versions :bdg-primary:`2025 R1 SP4` and :bdg-primary:`2025 R2 SP4`.

Known limitations
-------------------

- Only tested with ``pyaedt`` :bdg-primary:`1.0.1`. Using other versions may lead to unexpected behaviors.
- There should be an environment variable :envvar:`ANSYSEM_ROOTXXX` pointing to the AEDT installation directory.

  .. tab-set::

      .. tab-item:: Windows

          .. code:: powershell

              $Env:ANSYSEM_ROOT251="C:\Program Files\ANSYS Inc\v251\AnsysEM"
              $Env:ANSYSEM_ROOT252="C:\Program Files\ANSYS Inc\v252\AnsysEM"

      .. tab-item:: Linux

          .. code:: bash

              export ANSYSEM_ROOT251="/ansys_inc/v251/AnsysEM/"
              export ANSYSEM_ROOT252="/ansys_inc/v252/AnsysEM/"

- PyAEDT does not work for solutions that are deployed in a containerized manner.

- When connecting to a remote AEDT instance because AEDT is running in another server, PyAEDT requires to have AEDT installed locally in the client side. The license is not required.

- To use AEDT with HPS it is required to install the Python package ``ansys-saf-product-configuration[aedt]`` in the HPS scaler environment, and to include in the HPS scaler configuration both AEDT and its wrapper as available applications. For example, adding this snippet to the ``scaling_config.json``:

.. code:: json

    {
        "name": "Ansys Electronics Desktop",
        "version": "2025 R2",
        "install_path": "/ansys_inc/v252/AnsysEM/",
        "executable": "/ansys_inc/v252/AnsysEM/ansysedt",
    },
    {
        "name": "Ansys SAF Product Wrapper [AEDT]",
        "version": "2.0",
        "install_path": "<path-to-parent-dir-of-python-executable>",
        "executable": "<path-to-python-executable>",
    }

Note that the executable in the wrapper points to the Python that has the ``ansys-saf-product-configuration[aedt]`` package installed in its environment.

Example
--------

For a complete example using AEDT product managers, see the |aedt-example|_.


Fluent
=========

- ``Fluent3DDPSolverSecureManager``: supports secure gRPC connections.
- ``Fluent2DDPSolverSecureManager``: supports secure gRPC connections.
- ``Fluent3DDPMeshingSecureManager``: supports secure gRPC connections.
- ``Fluent3DDPSolverManager``: deprecated, use ``Fluent3DDPSolverSecureManager`` instead.
- ``Fluent2DDPSolverManager``: deprecated, use ``Fluent2DDPSolverSecureManager`` instead.
- ``Fluent3DDPMeshingManager``: deprecated, use ``Fluent3DDPMeshingSecureManager`` instead.

To be imported from ``ansys.saf.product_manager.fluent``.

Supported versions
-------------------

- Fluent versions :bdg-primary:`2025 R1 SP4` and :bdg-primary:`2025 R2 SP4`.

Known limitations
-------------------

- Only tested with ``ansys-fluent-core`` :bdg-primary:`0.37.0`. Using other versions may lead to unexpected behaviors.
- When the instance is re-initialized, the internal state of the fluent interpreter is not restored. Only files are restored.
- To use Fluent with HPS it is required to install the Python package ``ansys-saf-product-configuration[fluent]`` in the HPS scaler environment, and to include in the HPS scaler configuration both Fluent and its wrapper as available applications. For example, adding this snippet to the ``scaling_config.json``:

    .. code:: json

        {
            "name": "Ansys Fluent",
            "version": "2025 R2",
            "install_path": "/ansys_inc/v252/",
            "executable": "/ansys_inc/v252/fluent/bin/fluent",
        },
        {
            "name": "Ansys SAF Product Wrapper [Fluent]",
            "version": "4.0",
            "install_path": "<path-to-parent-dir-of-python-executable>",
            "executable": "<path-to-python-executable>",
        }

    Note that the executable in the wrapper points to the Python that has the ``ansys-saf-product-configuration[fluent]`` package installed in its environment.

- The secure managers support all gRPC transport modes described in :ref:`gRPC transport modes <instance_management_grpc_transport_modes>`. However, ``ansys-fluent-core`` enforces secure gRPC connections for local instances and does not permit insecure connections. This has two main implications:

    - **When using HPS**: To use insecure local connections, configure :envvar:`GLOW_PRODUCT_HOST` with your local IP address instead of localhost.
    - **When using PIM Light Server**: The only supported secure mode by PIM Light Server (``WNUA``) does not work. Because SAF GLOW Engine  cannot reliably know if ``WNUA`` or ``insecure`` mode is being used when using PIM Light Server (see :ref:`instance_management_grpc_transport_modes`), it falls back to insecure connections, which ``ansys-fluent-core`` rejects. As a workaround, configure :envvar:`GLOW_PRODUCT_HOST` with your local IP address instead of localhost to establish a connection.

Example
--------

For a complete example using Fluent product managers, see the |fluent-example|_.


Geometry
=============
- ``GeometrySecureManager``: supports secure gRPC connections.
- ``GeometryManager``: deprecated, use ``GeometrySecureManager`` instead.

To be imported from ``ansys.saf.product_manager.geometry``.

Supported versions
-------------------

- Windows: Geometry versions :bdg-primary:`2025 R1 SP4` and :bdg-primary:`2025 R2 SP4`.
- Linux: Geometry version :bdg-primary:`2025 R2 SP4`.

Configuration
--------------

- Install the Geometry service, following the steps proposed in the `GitHub issue <https://github.com/ansys/pyansys-geometry/discussions/1374>`_:

  - Download **only the first ISO image** of the Ansys official Release:

    .. figure:: /_static/images/install_geometry_1.png

  - Mount it and look in its content for the ``geometryservice/WINX64.7z`` file on Windows, or ``geometryservice/LINX64.TGZ`` on Linux. This compressed file contains the ``GeometryService`` directory that we want to install. Extract the ``WINX64.7z`` or ``LINX64.TGZ`` file, for example into: ``C:\Program Files\ANSYS Inc\v252\GeometryService`` or ``/ansys_inc/v252/GeometryService/``.

    .. figure:: /_static/images/install_geometry_2.png

- Upgrade to the latest service pack:

  - In the same page where you downloaded the first ISO image, download the latest service pack ISO image. You can find it at the bottom of the page.

    .. figure:: /_static/images/install_geometry_3.png

  - Locate and apply the service pack contents:

    - Extract the service pack ISO image.
    - Look for all directories that follow the format ``xxxxx_geometryservice``. There can be multiple ones if several service packs have been released.

    .. figure:: /_static/images/install_geometry_4.png

    - Within each of these directories, locate the ``WINX64.7z`` or ``LINX64.TGZ`` file and extract it, overwriting the existing ``GeometryService`` directory.
    - If there are multiple service packs, apply them sequentially, starting from the oldest to the newest.

- On Linux, make sure the ``licensingclient`` of the binaries has the right permissions:

  .. code:: bash

    chmod +x /ansys_inc/v252/GeometryService/licensingclient/linx64/ansyscl

- Requires configuring the environment variable :envvar:`GEOMETRY_ROOTXXX` to point to the ``GeometryService`` directory:

  .. tab-set::

      .. tab-item:: Windows

          .. code:: bash

              $Env:GEOMETRY_ROOT251="C:\Program Files\ANSYS Inc\v251\GeometryService"
              $Env:GEOMETRY_ROOT252="C:\Program Files\ANSYS Inc\v252\GeometryService"

      .. tab-item:: Linux

          .. code:: bash

              export GEOMETRY_ROOT252="/ansys_inc/v252/GeometryService/"

  This environment variable must be set in the Solution API process, even when HPS and Geometry are running in another environment. The value must be the valid one in the environment where Geometry is expected to run. For example, if Geometry is running on Windows and the Solution is running on Linux, the environment variable in the solution process would be: ``C:\Program Files\ANSYS Inc\v251\GeometryService``

- Requires configuring the environment variable :envvar:`ANSYSLMD_LICENSE_FILE` to point to a license server in the environment where Geometry is expected to run.

  .. code:: bash

      export ANSYSLMD_LICENSE_FILE="1055@my-host"`

- Requires `.NET 8.0 <https://dotnet.microsoft.com/en-us/download/dotnet/8.0>`_ or greater to be installed on the system, and to be added to the ``PATH`` environment variable. Using `dotnet-install scripts <https://dotnet.microsoft.com/en-us/download/dotnet/scripts>`_ is highly recommended.

- Requires modifying the HPS scaler configuration to add it as an available application ``scaling_config.json``:

  .. tab-set::

      .. tab-item:: Windows

          .. code:: json

              {
                  "name": "Ansys Geometry",
                  "version": "2025 R1",
                  "install_path": "<path-to-geometry-service-directory>",
                  "executable": "<path-to-geometry-service-directory>/Presentation.ApiServerDMS.exe",
              },
              {
                  "name": "Ansys Geometry",
                  "version": "2025 R2",
                  "install_path": "<path-to-geometry-service-directory>",
                  "executable": "<path-to-geometry-service-directory>/Presentation.ApiServerCoreService.exe",
              }

      .. tab-item:: Linux

          .. code:: json

              {
                  "name": "Ansys Geometry",
                  "version": "2025 R2",
                  "install_path": "<path-to-parent-dir-of-dotnet-executable>",
                  "executable": "<path-to-dotnet-executable>",
              }

- ``GeometrySecureManager`` supports all gRPC transport modes described in :ref:`gRPC transport modes <instance_management_grpc_transport_modes>`.

Known limitations
------------------

- Only tested with ``ansys-geometry-core`` :bdg-primary:`0.14.2`. Using other versions may lead to unexpected behaviors.


Example
----------

For a complete example using Geometry product manager, see the |geometry-example|_.


MAPDL
========

- ``MapdlSecureManager``: supports secure gRPC connections.
- ``MapdlManager``: deprecated, use ``MapdlSecureManager`` instead.

To be imported from ``ansys.saf.product_manager.mapdl``.

Supported versions
--------------------

- MAPDL versions :bdg-primary:`2025 R1 SP4` and :bdg-primary:`2025 R2 SP4`.

Known limitations
-----------------

- Only tested with ``ansys-mapdl-core`` :bdg-primary:`0.73.0`. Using other versions may lead to unexpected behaviors.
- Each MAPDL client created when interacting with the instance within a transaction spawns a new logger and adds it to the global logger.
  When the transaction ends, loggers are not cleaned up and keep accumulating. Hence, messages are duplicated except in the GLOW logger where they only appear once.
- MAPDL :bdg-primary:`2025 R1 SP4` and :bdg-primary:`2025 R2 SP4` are incompatible with the Database module of ``ansys-mapdl-core`` ``0.72.0``.
- MAPDL spawns a console window in the background when used in Windows.
- Concurrent instances of MAPDL in Windows are only supported using HPS.
- The secure manager supports all gRPC transport modes described in :ref:`gRPC transport modes <instance_management_grpc_transport_modes>`.

Example
---------

For a complete example using MAPDL product manager, see the |MAPDL-example|_.


Mechanical
===========

- ``MechanicalSecureManager``: supports secure gRPC connections.
- ``MechanicalManager``: deprecated, use ``MechanicalSecureManager`` instead.

To be imported from ``ansys.saf.product_manager.mechanical``.

Supported versions
------------------

- Mechanical versions :bdg-primary:`2025 R1 SP4` and :bdg-primary:`2025 R2 SP4`.

Known limitations
------------------

- Only tested with ``ansys-mechanical-core`` :bdg-primary:`0.12.0`. Using other versions may lead to unexpected behaviors.
- When the instance is re-initialized, the internal state of the mechanical interpreter is not restored. Only files are restored.
- HPS does not provide an official application finder. It requires a custom configuration to recognize Mechanical as an available application. For example, adding this snippet to the ``scaling_config.json``:
- The secure manager supports all gRPC transport modes described in :ref:`gRPC transport modes <instance_management_grpc_transport_modes>`, except ``UDS``.
  This means that for Linux, the only working secure mode is ``mTLS``.

.. code:: json

    {
        "name": "Ansys Mechanical",
        "version": "2025 R1",
        "install_path": "/ansys_inc/v251/aisol/",
        "executable": "/ansys_inc/v251/aisol/.workbench"
    }

Example
---------

For a complete example using Mechanical product manager, see the |mechanical-example|_.


optiSLang
=============

- ``OptislangManager``

To be imported from ``ansys.saf.product_manager.optislang``.

Supported versions
-------------------

- optiSLang versions :bdg-primary:`2024 R1` and :bdg-primary:`2024 R2`.

Known limitations
-----------------

- Only tested with ``ansys-optislang-core`` :bdg-primary:`0.9.4`. Using other versions may lead to unexpected behaviors.
- For :bdg-primary:`2024 R1`, it is not possible to import a project properties file. This should be fixed in :bdg-primary:`2024 R2`.
- It's recommended to use the same Python version as the one included in the optiSLang installation. Example: Python 3.11 for :bdg-primary:`2024 R1`.

Example
---------

For a complete example using optiSLang product manager, see the |optiSLang-example|_.


Visor
=====

- ``VisorManager``

To be imported from ``ansys.saf.product_manager.visor``.

Supported versions
-------------------

- Due to Visor's different nature than other flagship products and since it's still in development, SAF GLOW Engine  has :bdg-primary:`0` as the only supported version. This is meant to cover ``ansys-visor-viewer = ">=0.2.5b0, <1.0"``.


Known limitations
-------------------

- Only tested with ``ansys-visor-viewer`` :bdg-primary:`0.2.5b0`. Using other versions may lead to unexpected behaviors.
- HPS does not provide an official application finder. It requires a custom configuration to recognize Visor as an available application. For example, adding this snippet to the ``scaling_config.json``:

.. code:: json

    {
        "name": "Visor Viewer",
        "version": "0",
        "install_path": "<path-to-parent-dir-of-python-executable>",
        "executable": "<path-to-python-executable>",
    }

Note that the executable points to the Python that has the ``ansys-visor-viewer`` package installed in its environment.


How to use in your solution definition
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

See :ref:`instance_management_usage`.


How to extend for more products
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For more information, see :ref:`instance_management_custom`.
