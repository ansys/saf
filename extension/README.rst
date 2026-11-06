Solutions Manager extension (developer guide)
=============================================

Visual Studio Code extension that helps developers create and manage SAF solution applications.
This file is for contributors. End-user installation and usage instructions are in
`extension-instructions.md <extension-instructions.md>`_, which is packaged as the README of the VSIX.

The extension is a Node/TypeScript project. It is independent of SAF's Python packages: it is not part of the
root uv workspace, it is not built or published to PyPI, and it is versioned and released on its own.
The published extension identity stays ``Ansys.solutions-manager``.

Prerequisites
-------------

- Node.js as pinned in `.nvmrc <.nvmrc>`_, with the npm version that ships with it
- VS Code 1.109.0 or later
- Python 3.11-3.14 (the extension installs the SAF CLI into a managed virtual environment)
- On Windows, `long path support
  <https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation?tabs=registry>`_
  must be enabled

Set up
------

From the repository root:

.. code:: bash

    cd extension
    npm ci

Run the extension locally
-------------------------

#. Open the ``extension`` folder in VS Code (``code extension``), so that ``${workspaceFolder}`` is the
   extension root.
#. Create ``.vscode/launch.json`` (the ``.vscode`` folder is git-ignored):

   .. code:: json

       {
         "version": "0.2.0",
         "configurations": [
           {
             "name": "Run Extension",
             "type": "extensionHost",
             "request": "launch",
             "runtimeExecutable": "${execPath}",
             "args": ["--extensionDevelopmentPath=${workspaceFolder}"],
             "outFiles": ["${workspaceFolder}/out/**/*.js"],
             "preLaunchTask": "build"
           }
         ]
       }

#. Create ``.vscode/tasks.json``:

   .. code:: json

       {
         "version": "2.0.0",
         "tasks": [
           {
             "label": "build",
             "type": "shell",
             "command": "npm run compile",
             "group": "build",
             "options": { "cwd": "${workspaceFolder}" },
             "problemMatcher": []
           }
         ]
       }

#. Press F5. A new VS Code window opens with the extension loaded and the Solutions Manager view in the
   activity bar.

Checks
------

Run these from ``extension/``:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Purpose
   * - ``npm run typecheck``
     - Type-check sources and tests
   * - ``npm run lint:ci``
     - ESLint without auto-fix (``npm run lint`` applies fixes)
   * - ``npm run test:unit:coverage``
     - Unit tests with coverage
   * - ``npm run test:integration:coverage``
     - VS Code integration tests (downloads VS Code and installs the pinned SAF CLI)
   * - ``npm run package:vsix``
     - Compile and build ``dist/solutions-manager-<version>.vsix``

Integration tests need a display. On Linux run them under ``xvfb-run -a``. They also need network access to PyPI
and, on Windows, long paths enabled. They back up and restore the SAF CLI database.

The same tasks are available through Moon from the repository root:

.. code:: bash

    moon run extension:typecheck extension:lint extension:test-unit
    moon run extension:test-integration
    moon run extension:package-vsix

The Moon project disables the workspace Node and Python toolchains (the workspace Node toolchain is rooted in
``packages/saf-projects-dashboard``) and runs npm with the Node on your ``PATH``. CI calls npm directly in
``.github/workflows/_saf_solutions_manager.yml``.

Package the VSIX
----------------

``npm run package:vsix`` compiles the extension and runs ``scripts/package-vsix.mjs``, which:

#. Stages the manifest, the compiled bundle (``out/extension.js``, ``out/webview/``), the icon, the license and
   the changelog in ``.vsix-staging/``.
#. Writes ``extension-instructions.md`` into the staging directory as ``README.md``. This developer README is
   never packaged.
#. Fails if a required file is missing, then builds the VSIX with a pinned ``@vscode/vsce``.

Install the result with ``code --install-extension dist/solutions-manager-<version>.vsix``.

SAF CLI version
---------------

The extension installs a pinned, published ``ansys-saf-cli`` from PyPI, not a CLI built from this checkout. The
pin is ``SAF_CLI_VERSION`` in `src/utils/safCliVersion.ts <src/utils/safCliVersion.ts>`_. Bump it when moving to
a new SAF CLI release.

Versioning and release
----------------------

The extension version lives in ``package.json`` and ``package-lock.json`` and is independent of the SAF Python
packages. To change it:

.. code:: bash

    npm version <new-version> --no-git-tag-version

Releases use ``.github/workflows/ci_cd_saf_solutions_manager_release.yml`` (manual dispatch from ``main`` or
``release/**``). It checks that the requested version matches ``package.json``, runs the certification workflow
(``saf_solutions_manager_certification.yml``: checks, ``npm audit``, license allowlist, SBOM), and attaches the
VSIX to a GitHub Release tagged ``saf-solutions-manager-v<version>``. Publishing to the VS Code Marketplace is
not automated.

Contributing
------------

Repository-wide rules apply: see the root `CONTRIBUTING.md <../CONTRIBUTING.md>`_ and
`SECURITY.md <../SECURITY.md>`_.

License
-------

Apache 2.0. See `LICENSE <LICENSE>`_.
