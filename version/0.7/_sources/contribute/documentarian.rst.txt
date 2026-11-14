.. _contribute_doc:

Contribute as a documentarian
#############################

Anybody can contribute to the documentation by writing new content, reviewing and editing existing content, and flagging errors or outdated information.

.. _write-documentation:

Write documentation
===================

The documentation generator used in SAF is `Sphinx`_. Most of the documents
are written in `reStructuredText`_.

The ``saf`` repository hosts two kinds of documentation:

- The centralized documentation, located in the ``doc`` directory at the root of
  the repository. It contains the overview, the getting started guide, the user
  guide, the examples, and this contribution guide.
- The API documentation of a package, located in the ``doc`` directory of that
  package, under ``packages/<package-name>/doc``. Only the packages that expose
  a public API declare such a directory.

The centralized documentation is located in the ``doc/source`` directory. The
landing page is declared in the ``doc/source/index.rst`` file. The rest of the
files contain the main pages of different sections of the documentation.
Finally, the ``doc/source/_static/`` folder contains various assets like images,
and CSS files.

The layout of the ``doc/source`` directory is reflected in the slug of the
online documentation. For example, the
``doc/source/contribute/documentarian.rst`` renders as
``https://saf.ansys.com/version/stable/contribute/documentarian``.

Thus, if you create a new file, it is important to follow these rules:

- Use lowercase letters for file and directory names
- Use short and descriptive names
- Use hyphens to separate words
- Play smart with the hierarchy of the files and directories

All files need to be included in a table of contents. No dangling files are
permitted. If a file is not included in the table of contents, Sphinx raises a
warning that makes the build to fail.

A table of contents can be declared using a directive like this:

.. code-block:: rst

    .. toctree::
        :hidden:
        :maxdepth: 3

        path-to-file-A
        path-to-file-B
        path-to-file-C
        ...

The path to the file is relative to the directory where the table of contents
is declared.

.. _build_the_documentation:

Build the documentation
=======================

Build the documentation locally to review it before publishing. You can build the centralized SAF documentation or the API documentation of a package.

Centralized documentation
-------------------------

The dependencies of the centralized documentation are declared in the ``doc``
group of the root ``pyproject.toml`` file. Moon installs the configured
toolchains, including uv, and runs the build from the repository root:

.. code-block:: text

    moon run root:build-doc

The generated documentation is available in the ``doc/_build/html`` directory.
Open the ``doc/_build/html/index.html`` file in a web browser to review it.
The search bar and the version selector are not available in the local build.

API documentation of a package
------------------------------

The dependencies of the API documentation of a package are declared in the
Package API documentation is built with the Moon task configured for that
package. From the repository root, run:

.. code-block:: text

    moon run <project-name>:build-doc

Use ``moon projects`` to find the project name. The task installs and invokes
the documentation dependencies through the uv workspace.

.. _check_the_documentation_style:

Check the documentation style
=============================

The style of the documentation is checked with `Vale`_. The configuration and
the accepted vocabulary are declared in the ``doc/.vale.ini`` file and in the
``doc/styles`` directory. The same check runs in the CI/CD pipelines on every
pull-request that touches the documentation.
