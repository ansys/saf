.. _test_quick_start:

Quick start guide
###################

Install required fixtures
=========================

SAF GLOW Engine's testing fixtures only require ``pytest`` and ``pytest-mock`` as dependencies. Make sure they are in your ``pyproject.toml`` file:

For Poetry-based solutions:

.. code-block:: toml

   [tool.poetry.group.tests]
   optional = true
   [tool.poetry.group.tests.dependencies]
   pytest = "^9.0"
   pytest-mock = "^3.15"

For UV-based solutions, add the requirements to the existing ``tests`` list under
``[dependency-groups]``:

.. code-block:: toml

   [dependency-groups]
   tests = ["pytest>=9.0,<10", "pytest-mock>=3.15,<4"]

Install extra fixtures
=========================

Alternatively, you can use the ``"core-test"`` extra in the ``ansys-saf-sdk`` dependency. This extra installs
``pytest`` and ``pytest-mock``, with the appropriate versions, and any future required dependency.

For Poetry-based solutions:

.. code-block:: toml

   [tool.poetry.group.tests]
   optional = true
   [tool.poetry.group.tests.dependencies]
   ansys-saf-sdk = { version = "^0.2.0", extras = ["core-test"] }

For UV-based solutions, add the SDK requirement with ``core-test`` to the ``tests``
group. Use the same SDK version constraint as in the rest of the solution:

.. code-block:: toml

   [dependency-groups]
   tests = ["ansys-saf-sdk[core-test]>=0.4.0,<1.0.0"]

From the solution root, update the UV lock file and install the test dependencies:

.. code-block:: bash

   uv lock
   saf install -d tests

Include any other groups your tests need in the ``-d`` list.

Pytest automatically discovers the GLOW fixture plugin, ``ansys.saf.glow.testing``. Do not import fixture modules or
declare ``pytest_plugins`` in your test suite.
