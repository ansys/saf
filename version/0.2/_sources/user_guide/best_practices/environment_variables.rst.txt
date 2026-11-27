.. _best_practices_environment_variables:

#####################
Environment variables
#####################

This section explains how to properly access environment variables in a SAF-based solution application.

.. warning::

   Do **not** call ``load_dotenv()`` in your solution code. SAF already loads the ``.env`` file at startup
   and injects the variables into the process environment.

Why ``load_dotenv()`` must not be used
======================================

A common but **incorrect** pattern observed in solution code is:

.. code-block:: python

   import os
   from dotenv import load_dotenv

   load_dotenv()

   MY_VARIABLE = os.getenv("MY_VARIABLE")

This pattern appears to work during development (``saf run``) because the current working directory is
the solution root, where the ``.env`` file resides. However, in production (installed or deployed solution),
the working directory differs and the ``.env`` file is not found at the expected path. As a result,
``load_dotenv()`` silently does nothing and all variables resolve to ``None``.

SAF handles ``.env`` loading for you — the framework reads the file at startup and populates the process
environment before your solution code executes. Manually calling ``load_dotenv()`` is therefore redundant
in development and broken in production.

Recommended patterns
====================

Use ``os.getenv()``
---------------------

The simplest approach is to read variables directly from the environment:

.. code-block:: python

   import os


   class MyStep:
       def __init__(self):
           self.my_variable = os.getenv("MY_VARIABLE")

Avoid calling ``os.getenv()`` at module import time (i.e., at the top level of a module). Instead,
place these calls inside methods or class ``__init__`` methods where the values are actually used.
This protects against race conditions where the variable is read before SAF has finished loading
the ``.env`` file into the process environment.


Use Pydantic Settings (preferred)
------------------------------------

For validation, type safety, and default values, use
`pydantic-settings <https://docs.pydantic.dev/latest/concepts/pydantic_settings/>`_:

.. code-block:: python

   from pydantic_settings import BaseSettings


   class MySettings(BaseSettings):
       my_variable: str
       my_optional_variable: str = "default_value"


   settings = MySettings()  # Reads from environment automatically

Field names are mapped directly to environment variable names in upper case. In the example above,
``my_variable`` reads from the ``MY_VARIABLE`` environment variable and ``my_optional_variable`` reads
from ``MY_OPTIONAL_VARIABLE``.

This approach provides:

- **Type coercion**: Values are automatically cast to the declared type.
- **Validation**: Missing required variables raise a clear error at startup rather than silently returning ``None``.
- **Default values**: Optional variables can have sensible defaults.
- **Documentation**: The settings class serves as a single source of truth for all expected environment variables.

Summary
=======

.. list-table::
   :header-rows: 1
   :widths: 50 25 25

   * - Pattern
     - Development (``saf run``)
     - Production (installed/deployed)
   * - ``load_dotenv()`` + ``os.getenv()``
     - ✅ Works
     - ❌ Fails silently
   * - ``os.getenv()`` only
     - ✅ Works
     - ✅ Works
   * - Pydantic Settings
     - ✅ Works
     - ✅ Works
