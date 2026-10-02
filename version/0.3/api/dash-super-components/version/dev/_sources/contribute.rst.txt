.. _ref_contribute:

Contribute
##########

Overall guidance on contributing to a PyAnsys library appears in the
`Contributing <https://dev.docs.pyansys.com/how-to/contributing.html>`_ topic
in the *PyAnsys developer's guide*. Ensure that you are thoroughly familiar
with this guide before attempting to contribute to this project.

The following sections provide repository-specific instructions.

Developer setup
===============

.. vale Google.Headings = NO

Prerequisites
-------------

.. vale Google.Headings = YES

Before setting up a development environment, ensure you have the following
installed:

- Python 3.11 to 3.14. Higher versions may work but are not officially supported.
- Poetry 2.3.2 or newer

To install the minimum required Poetry version, run:

.. code-block:: bash

   pipx install "poetry>=2.3.2"

Clone the repository
--------------------

Clone the repository to your local machine:

.. code-block:: bash

   git clone https://github.com/ansys/super-components-for-dash.git
   cd super-components-for-dash

Installing the development environment
---------------------------------------

Set up the development virtual environment by running:

.. tabs::

   .. code-tab:: bat
      :caption: CMD/PowerShell

      poetry install --with tests,doc,style

   .. code-tab:: bash
      :caption: Bash

      poetry install --with tests,doc,style

This creates a ``.venv`` virtual environment in the repository root with all
dependencies installed (package, tests, docs, and style checks).

Activate the virtual environment before running any commands:

.. tabs::

   .. code-tab:: bat
      :caption: PowerShell

      .\.venv\Scripts\Activate.ps1

   .. code-tab:: bat
      :caption: CMD

      .\.venv\Scripts\activate.bat

   .. code-tab:: bash
      :caption: Bash

      source .venv/bin/activate

Running tests
=============

Tests are located in the ``tests/`` directory and are run with
`pytest <https://pytest.org>`_.

After activating the virtual environment, run the full test suite via ``tox``:

.. code-block:: bash

   poetry run tox -e tests

Alternatively, you can run tests directly with `pytest`:

.. code-block:: bash

   pytest

To run tests with coverage reporting:

.. code-block:: bash

   pytest --cov=ansys.solutions.dash_super_components --cov-report=term --cov-report=html:.cov/html

Test coverage
-------------

All new features and bug fixes must be accompanied by tests. The minimum
required coverage for new code is 80%, but the goal should be significantly
higher. Tests should be placed in the ``tests/unit/`` directory following the
same module structure as the source code.

Running style checks
====================

Style checks are enforced using `pre-commit <https://pre-commit.com/>`_. Run
all style checks via ``tox``:

.. code-block:: bash

   poetry run tox -e style

Or run ``pre-commit`` directly:

.. code-block:: bash

   pre-commit run --all-files --show-diff-on-failure

Coding style
------------

Follow the `PEP 8 <https://peps.python.org/pep-0008/>`_ style guide. All
Python code is automatically checked by ``ruff`` and ``pyright``. Type hints
are required for all public function and method signatures.

Docstrings must follow the
`PyAnsys docstring guidelines <https://dev.docs.pyansys.com/doc-style/docstrings.html>`_
(numpydoc format). Refer to the existing components for examples of the
expected format.

.. vale Google.Headings = NO

Build the documentation locally
===============================

.. vale Google.Headings = YES

Documentation is built with `Sphinx <https://www.sphinx-doc.org/>`_.
Build the HTML documentation via ``tox``, or directly using ``make``.
Clean the build directory beforehand to ensure a fresh build.

.. tabs::

   .. code-tab:: bat
      :caption: CMD/PowerShell (tox)

      poetry run tox -e doc-clean
      poetry run tox -e doc-html

   .. code-tab:: bash
      :caption: Bash (tox)

      poetry run tox -e doc-clean
      poetry run tox -e doc-html

   .. code-tab:: bat
      :caption: CMD/PowerShell (make)

      doc\make.bat clean
      doc\make.bat html

   .. code-tab:: bash
      :caption: Bash (make)

      make -C doc clean
      make -C doc html

The rendered documentation is written to ``doc/_build/html/``. Open
``doc/_build/html/index.html`` in a browser to preview it.

Documentation style
-------------------

Documentation prose is checked by `Vale <https://vale.sh/>`_ against the
Google developer documentation style guide. Before running Vale for the first
time, synchronize the necessary rulesets:

.. code-block:: bash

   vale --config=doc/.vale.ini sync

Then run Vale to check documentation:

.. code-block:: bash

   vale --config=doc/.vale.ini doc/source

All RST documentation must follow the
`PyAnsys documentation guidelines <https://dev.docs.pyansys.com/doc-style/doc-guidelines.html>`_.

Contributing examples
=====================

Example solutions are located in the ``examples/`` folder. Currently, the
``examples/showcase_all/`` example solution demonstrates the usage of all
available components in a single application.

New example solutions can be added in the ``examples/`` folder. Each new
example solution must include a ``README.md`` with instructions for setup
and usage.

Format
------

Each page in the showcase application corresponds to a single component. When
adding an example for a new component:

1. Add a new page file under
   ``examples/showcase_all/src/ansys/solutions/showcase_dash_super_components/ui/pages/``.
2. Follow the naming convention ``<component_name>_page.py``.
3. Register the new page in the ``display_page`` callback in
   ``examples/showcase_all/src/ansys/solutions/showcase_dash_super_components/ui/pages/page.py``.

Verification
------------

Before submitting an example:

1. Run the showcase application locally and verify that the new page renders
   correctly.
2. Confirm there are no callback errors. Run the application with the
   ``--debug`` flag to see callback errors if they occur.
3. Confirm that all component interactions work as expected.

README file requirement
-----------------------

Each example page in the showcase application should be self-contained and
well-commented. If you add a standalone example solution outside the showcase
application, include a ``README.md`` in the example directory that explains:

- What the example demonstrates.
- How to install dependencies.
- How to run the example.

Opening a pull request
======================

Before opening a pull request, ensure that:

- All tests pass (``poetry run tox -e tests``).
- All style checks pass (``poetry run tox -e style``).
- Documentation builds without errors (``poetry run tox -e doc-html``).
- Documentation style check passes (``vale --config=doc/.vale.ini doc/source``)
- New features include tests.
- New or changed components include updated documentation in
  ``doc/source/user-guide/``.
- The pull request description explains the motivation, summarizes the changes
  made, and references the issue that the pull request addresses.

