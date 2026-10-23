.. _test_e2e:

End-to-end testing
##################

End-to-end (E2E) tests validate a complete user journey through a packaged
solution. Unlike the :ref:`test` fixtures, which use an in-process test client,
these tests exercise the real SAF lifecycle:

* install the solution with ``saf install``;
* build a desktop installer with ``saf build``;
* install and launch the generated application;
* wait for the Solution API and UI; and
* open the UI in a real Chrome browser.

The reference implementation is in
`examples/tests/e2e
<https://github.com/ansys/saf/tree/main/examples/tests/e2e>`__.
It is also the recommended starting point for adding E2E tests to another SAF
solution.

Prerequisites
=============

Run the tests from the Python environment used to install the solution. The
environment must provide:

* Python with a version between 3.11 and 3.14 included, supported by the solution. The examples solution currently supports
  Python 3.11 and 3.12;
* the SAF CLI, available as ``saf`` on ``PATH`` or through the
  ``SAF_EXECUTABLE`` environment variable;
* ``pytest``, ``selenium``, ``psutil``, and ``httpx2``;
* Chrome or Chromium and a compatible WebDriver. Selenium Manager can provide
  the driver when it is supported by the local installation; and
* the solution's desktop and UI dependencies. The fixture installs the build
  dependencies in the temporary solution workspace.

For the examples solution, run these commands from the ``examples`` directory
to create the lock file and install the test environment:

.. code-block:: console

   saf execute "poetry lock"
   saf execute "poetry install --with tests,desktop,ui"

The E2E fixture copies the solution to a temporary workspace and explicitly
installs its ``desktop``, ``ui``, and ``build`` groups with:

.. code-block:: console

   saf install -f -d desktop,ui,build

This is the command used inside that temporary workspace. Do not run it with
``-f`` in the same checkout after installing the test environment: it removes
the checkout's ``.venv`` and can remove the ``pytest`` and ``saf`` executables
used to run the tests.

The ``tests`` group is for the environment that runs pytest and the SAF CLI.
It is not installed in the temporary solution workspace because the fixture
does not copy the ``tests`` directory there. The dependency check reuses the
same ``desktop``, ``ui``, and ``build`` group list when it asks Poetry to
report installed packages.

The E2E tests use ``saf install`` and ``saf build``, then run the generated
installer directly. The CI environment does not provide SAF CLI by default,
so the examples test group declares ``ansys-saf-cli``. This installs SAF CLI
console script in the same environment as pytest.

In the SAF repository, use the local SAF CLI package:

.. code-block:: toml

   [tool.poetry.group.tests.dependencies]
   ansys-saf-cli = { path = "../packages/saf-cli", develop = true }

For a standalone solution, install a released SAF CLI version compatible with the
solution instead of using the repository path dependency. Verify that SAF CLI
is available:

.. code-block:: console

   saf --version

If SAF CLI must be selected explicitly, set
``SAF_EXECUTABLE`` to its full path before starting pytest. In
PowerShell, for example:

.. code-block:: powershell

   $env:SAF_EXECUTABLE = "C:\path\to\saf.exe"

On Linux, tests that launch the desktop shortcut additionally require
``gtk-launch`` and ``xvfb-run``. On Debian-based systems, install them with:

.. code-block:: console

   sudo apt update
   sudo apt install libgtk-3-bin xvfb

The splash-screen assertion is skipped on Linux because the current desktop
orchestrator displays that splash only on Windows. On Windows, the test waits
for the orchestrator's selected PNG path and verifies that it is the solution's
custom splash image when present, or the built-in orchestrator splash image
otherwise.

Run the suite
=============

Run collection first. This checks imports and fixture names without installing
or launching the solution:

.. code-block:: console

   saf execute "pytest --collect-only -q tests/e2e"

Then run the complete suite from the solution root:

.. code-block:: console

   saf execute "pytest tests/e2e"


You can run lifecycle stages individually when diagnosing a failure:

.. code-block:: console

   saf execute "pytest -q tests/e2e/test_install_dependencies.py"
   saf execute "pytest -q tests/e2e/test_build_installer.py"
   saf execute "pytest -q tests/e2e/test_execute_installer.py"
   saf execute "pytest -q tests/e2e/test_execute_shortcut.py"
   saf execute "pytest -q tests/e2e/test_solution_ui.py"

For detailed setup, command output, and timing information, use:

.. code-block:: console

   saf execute "pytest tests/e2e -vv -s --setup-show --durations=0 --log-cli-level=INFO"

Use ``--log-cli-level=DEBUG`` to include the output captured from
``saf install``, ``saf build``, and the desktop installer.

Test structure
==============

The shared setup in
`tests/e2e/conftest.py
<https://github.com/ansys/saf/tree/main/examples/tests/e2e/conftest.py>`__
passes the solution through isolated lifecycle stages. The session-scoped
application fixture chain is:

.. code-block::

   examples_test_environment
       -> examples_workspace
       -> installed_examples
       -> built_examples
       -> installed_desktop_examples
       -> launched_examples
       -> running_examples

The browser fixture is independent from the application fixture chain:

.. code-block::

   examples_chrome_options
       -> examples_webdriver

The UI tests use both ``running_examples`` and ``examples_webdriver``. On Linux,
``launched_examples`` also checks that ``gtk-launch`` and ``xvfb-run`` are
available before opening the desktop shortcut.

The temporary environment redirects application state (including ``APPDATA``,
``HOME``, and the XDG directories) to temporary folders. The source solution is
copied to a temporary workspace before installation and build, so the tests do
not modify the developer's checkout. The launched process and its child
processes are stopped during fixture teardown.

The reference test modules cover these stages:

``test_install_dependencies.py``
   ``test_saf_install_completes_successfully`` runs
   ``saf install -f -d desktop,ui,build`` and checks that the virtual
   environment and lock file were created. Then
   ``test_saf_install_verifies_locked_dependencies`` runs ``poetry show`` for
   ``main``, ``desktop``, ``ui``, and ``build`` and verifies that every locked
   package is installed.

``test_build_installer.py``
   ``test_saf_build_creates_desktop_installer`` runs ``saf build`` and checks
   that the platform-specific installer exists, is non-empty, and is executable
   on Linux.

``test_execute_installer.py``
   ``test_generated_installer_executes_without_errors`` runs the installer with
   ``--no-ui`` and a temporary installation directory, then checks for a
   deployed ``version.txt`` file.

``test_execute_shortcut.py``
   ``test_desktop_shortcut_is_created`` checks the generated Windows ``.lnk`` or
   Linux ``.desktop`` shortcut. The
   ``test_shortcut_launches_solution_and_validates_splash_image`` test verifies
   on Windows that the shortcut starts the solution, reports the expected PNG
   splash image, and selects a valid image. That splash assertion is skipped on
   Linux, where shortcut launching is exercised by the UI fixtures.

``test_solution_ui.py``
   ``test_solution_ui_is_accessible_in_browser`` opens a temporary project in
   Chrome, waits for the Dash page to render, and checks browser console and
   network diagnostics. Then
   ``test_discovered_pages_render_without_browser_failures`` discovers
   navigation pages at runtime, expands navigation groups, and visits every
   visible leaf page instead of maintaining a hardcoded route list. It collects
   all page failures before reporting them. Chrome navigation uses an eager
   page-load strategy, followed by an explicit wait for rendered page content,
   so a background resource cannot prevent a usable page from being checked.

Implement E2E tests
======================

Start by copying the reference ``tests/e2e`` package and its package marker
files, ``tests/__init__.py`` and ``tests/e2e/__init__.py``. Keep the shared
lifecycle in ``conftest.py`` and put assertions in the test module for the
lifecycle stage or feature they verify.

Adapt these solution-specific values first:

* the solution root copied by ``examples_workspace``;
* the display name and platform-specific shortcut path;
* the installer output directory and filename;
* the installer arguments and a stable deployed-file marker;
* the log patterns used to find the API and UI URLs; and
* the API request used to create a temporary project.

The reference project assumes that project creation uses:

.. code-block::

   POST <solution-api>/projects
   {"display_name": "<unique name>"}

and returns a resource named ``projects/<id>``. Replace
``_create_project`` when the solution has a different API contract or no
project concept.

For browser checks, retain explicit waits rather than fixed sleeps. The
reference helpers wait for the standard SAF layout containers
``#navbar-content`` and ``#page-content``. Update these selectors and the
navigation-group helpers if the solution uses a different layout. The dynamic
page smoke test confirms that pages render without JavaScript console errors,
HTTP errors, or failed network requests; it does not replace feature-specific
tests for buttons, forms, uploads, or business workflows.

Keep every test isolated:

* install and build in a temporary copy of the solution;
* use a temporary installation directory and project;
* clear browser logs before each page navigation;
* collect diagnostics after the page has rendered; and
* stop the complete application process tree in a ``finally`` block.

Continuous integration
======================

When a change affects the examples solution, the PR workflow runs the automated
E2E test matrix defined in
`.github/workflows/tests_groups_definitions/examples.json
<https://github.com/ansys/saf/blob/main/.github/workflows/tests_groups_definitions/examples.json>`__.
The same suite runs on ``windows-latest`` and ``ubuntu-latest`` to check the
desktop lifecycle on both supported platforms.

For each operating system, the CI workflow:

#. prepares the Poetry environment with the ``tests``, ``desktop``, and ``ui``
   dependency groups;
#. installs PIM Light Server for the E2E environment;
#. installs ``gtk-launch`` and ``xvfb-run`` on Linux;
#. runs pytest, which exercises ``saf install``, ``saf build``, the generated
   installer, the desktop shortcut, the API and UI services, and the browser
   page checks; and
#. publishes the pytest reports and logs as workflow artifacts.

The PIM package is installed in the pytest environment. The E2E harness adds
that environment's ``site-packages`` to ``PYTHONPATH`` for the generated
installer and launched desktop process because the packaged application uses a
separate virtual environment. When using a sparse checkout, include
``packages/saf-cli`` as well as ``examples`` because the examples test group
declares SAF CLI as a local Poetry path dependency.

Troubleshooting
===============

* **SAF CLI not found:** run ``saf --version`` in the pytest environment or set
  ``SAF_EXECUTABLE``.
* **Installer not found:** update the expected filename in
  ``_get_installer_path``.
* **Shortcut not found:** update the solution display name and platform-specific
  desktop path.
* **API/UI timeout:** check the URL patterns and platform-specific Glow log
  directory used by ``running_examples``.
* **No pages discovered:** inspect the rendered DOM and update the navigation
  selectors or group detection helpers.
* **Linux launch failure:** install ``gtk-launch`` and ``xvfb-run`` or replace
  the Linux launcher with the solution's supported mechanism.
* **Chrome startup failure:** inspect the ChromeDriver log named in the pytest
  error. The fixture uses a fresh temporary Chrome profile for each retry.
* **Dependency verification failure:** compare the ``saf install`` dependency
  groups with the groups reported by ``poetry show`` and check that the
  solution's lock file is current.
* **Processes remain after pytest:** verify that the launcher teardown stops the
  parent and all child processes.