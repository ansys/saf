.. _test_quick_start:

Quick start guide
###################

Install required fixtures
=========================

SAF GLOW Engine's testing fixtures only require ``pytest`` and ``pytest-mock`` as dependencies. Make sure they are in your ``pyproject.toml`` file:

.. code-block:: toml

   [tool.poetry.group.tests]
   optional = true
   [tool.poetry.group.tests.dependencies]
   pytest = "^9.0"
   pytest-mock = "^3.15"

Install extra fixtures
=========================

Alternatively, you can use the ``"core-test"`` extra in the ``ansys-saf-sdk`` dependency. This extra installs
``pytest`` and ``pytest-mock``, with the appropriate versions, and any future required dependency.

.. code-block:: toml

   [tool.poetry.group.tests]
   optional = true
   [tool.poetry.group.tests.dependencies]
   ansys-saf-sdk = { version = "^0.2.0", extras = ["core-test"] }

Pytest automatically discovers the GLOW fixture plugin, ``ansys.saf.glow.testing``. Do not import fixture modules or
declare ``pytest_plugins`` in your test suite.
