.. _instance_management_grpc_transport_modes:

gRPC transport modes
####################

This section summarizes the supported gRPC transport modes between SAF GLOW Engine and product instances. These modes apply to product configurations that have ``enable_secure_flags=True``, which is the case for all built-in product instance managers except ``VisorManager``.

.. important::

    Custom product configurations use insecure gRPC connections by default to avoid breaking changes. To benefit from the supported secure connection modes, set ``enable_secure_flags=True`` in your product configuration. For more information, see :ref:`instance_management_custom`.


Supported modes by product instance system
==========================================

The effective transport mode depends on:

- Product instance system: ``PIM Light Server`` or ``HPS``.
- Operating system of the product instance.
- Product binding host (localhost vs non-localhost).
- Availability of gRPC certificates.

.. list-table:: Supported gRPC transport modes
   :header-rows: 1
   :stub-columns: 1

   * - Product instance system
     - Product host scenario
     - Supported mode
     - Required configuration
   * - ``PIM Light Server``
     - Windows + localhost binding
     - ``WNUA``
     - No certificate directory required.
   * - ``PIM Light Server``
     - Any other scenario
     - ``insecure``
     - No secure mode currently supported.
   * - ``HPS``
     - Windows + localhost binding
     - ``WNUA``
     - No certificate directory required.
   * - ``HPS``
     - Linux + localhost binding
     - ``UDS``
     - No certificate directory required.
   * - ``HPS``
     - Windows or Linux + non-localhost binding, certificates available
     - ``mTLS``
     - Requires certificate directory.
   * - ``HPS``
     - Windows or Linux + non-localhost binding, certificates not available
     - ``insecure``
     - This behavior is a compatibility fallback.

.. important::

    When using ``PIM Light Server``, even if ``WNUA`` is used, SAF GLOW Engine logs that insecure gRPC connections is being used. This is because SAF GLOW Engine doesn't have enough information to reliably say if the product is running with ``WNUA`` or in ``insecure`` mode. Nevertheless, in the products instance output, you can verify that it's running with ``WNUA``.

These modes describe the product instance system capabilities. However, the actual transport availability also depends on the capabilities of the product and its client. Check the notes for each product in :ref:`instance_management_supported_products`.


Configuration variables
========================

- Use :envvar:`GLOW_PRODUCT_BINDING_HOST` to control whether the product binds to localhost or a non-localhost IP. This is set in the environment where the product instance is running, **NOT** in the GLOW API environment. For HPS, set it in the process that launches the HPS evaluator or scaler. When using products with ``secure_flags`` enabled, it defaults to ``localhost``, which enables either ``WNUA`` or ``UDS`` modes depending on the operating system. On the other hand, in insecure products, it defaults to all interfaces (``0.0.0.0``) to avoid breaking changes.

  Product instances bound to ``localhost`` are only reachable from the same system. When SAF GLOW Engine runs in a different system or container, set it to a non-localhost address, such as the IP of the system or ``0.0.0.0``.

  The following products don't bind to the exact configured address:

  - MAPDL binds to localhost for localhost values, and to all interfaces otherwise.
  - Visor always binds to all interfaces (``0.0.0.0``).

- Use :envvar:`ANSYS_GRPC_CERTIFICATES` to enable ``mTLS`` in non-localhost scenarios. Certificates directory must contain:

  - ``client.crt``
  - ``client.key``
  - ``ca.crt``

Related configuration
======================

For full product instance management setup, see :ref:`instance_management_configuration`.
