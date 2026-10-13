##########################################
Solution Application Framework - Templates
##########################################

|python| |pypi| |GH-CI| |codecov| |Apache| |ruff|

.. |python| image:: https://img.shields.io/pypi/pyversions/ansys-saf-templates?logo=python&logoColor=white&label=Python
   :target: https://pypi.org/project/ansys-saf-templates/
   :alt: Python

.. |pypi| image:: https://img.shields.io/pypi/v/ansys-saf-templates.svg?logo=pypi&logoColor=white&label=PyPI
   :target: https://pypi.org/project/ansys-saf-templates/
   :alt: PyPI

.. |GH-CI| image:: https://img.shields.io/github/actions/workflow/status/ansys/saf/ci_cd_pr.yml?branch=main&label=CI-CD&logo=github
   :target: https://github.com/ansys/saf/actions/workflows/ci_cd_pr.yml?query=branch%3Amain
   :alt: GH-CI

.. |codecov| image:: https://img.shields.io/codecov/c/github/ansys/saf?flag=saf-templates
   :target: https://app.codecov.io/gh/ansys/saf?flags[0]=saf-templates
   :alt: Codecov

.. |Apache| image:: https://img.shields.io/badge/License-Apache2.0-white.svg?labelColor=black
   :target: https://www.apache.org/licenses/
   :alt: Apache

.. |ruff| image:: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
   :target: https://github.com/astral-sh/ruff
   :alt: Ruff


Overview
========

**SAF Templates** is a collection of Cookiecutter-based templates that help
developers quickly scaffold common components for SAF-based solution
applications. Instead of writing boilerplate code from scratch, developers can
generate ready-to-use solution steps, pages, and supporting files through the
SAF CLI, then customize them to fit their specific use case.

The package currently ships the following built-in step templates:

+---------------------------------+------------------------------------------------------+---------+
| Template name                   | Description                                          | Owner   |
+=================================+======================================================+=========+
| ``calculator-step``             | A step that performs basic calculator operations.    | SAF-SDK |
+---------------------------------+------------------------------------------------------+---------+
| ``hps-simple-job-step``         | A step that submits a simple job to HPS.             | SAF-SDK |
+---------------------------------+------------------------------------------------------+---------+
| ``hps-parametric-study-step``   | A step that runs a parametric study on HPS.          | SAF-SDK |
+---------------------------------+------------------------------------------------------+---------+
| ``instance-mgmt-geometry-step`` | A step for basic Geometry instance management.       | SAF-SDK |
+---------------------------------+------------------------------------------------------+---------+

Beyond the built-in templates, SAF Templates supports a **plugin architecture**
that allows developers and teams to create, package, and share their own
template repositories. This means you can build reusable templates tailored to
your organization's patterns and distribute them across projects or to the
wider community.

Contributions are welcomed. If you have a useful template that could benefit
other SAF developers, consider contributing it back to the project or
publishing your own template plugin repository.


Installation
============

Ensure you have all the necessary `prerequisites`_.

SAF Templates comes bundled with SAF CLI since SAF CLI version 3.7. However, **it is
mandatory to have SAF CLI version 4.0.1 or later installed to use the templates**.
Using previous versions of SAF CLI might produce unexpected results or even errors
when attempting to add a step. This documentation assumes that SAF CLI version 4.0.1 or
later is installed.

Use the following command if you want to manually install a newer version of the SAF
Templates package. Make sure to install it in the python environment where SAF CLI is
installed:

.. code-block:: bash

    pip install ansys-saf-templates


Documentation
=============

Visit the `official documentation`_ for detailed information on how to use SAF Templates.
Browse the `Template gallery`_ for all available templates.

Quick start
-----------

You can list the available templates by running:

.. code-block:: bash

    saf templates

This will show all the templates available in ansys-saf-templates as well as any
additional templates from installed plugins.

Add a new step to your solution using the SAF CLI command:

.. code-block:: bash

    saf add-step <my_solution>

The CLI will interactively guide you through selecting a template and providing
the required parameters. Otherwise, you can directly pass all the necessary
information as command-line arguments:

.. code-block:: bash

    saf add-step <my_solution> --step-name <step_name> --ui-framework <ui_framework> --template <template_name>


Troubleshooting
===============

For troubleshooting or reporting issues, please open an issue in the `project repository`_.

Please follow these steps to report an issue:

- Go to the project repository.
- Click on the ``Issues`` tab.
- Click on the ``New Issue`` button.
- Provide a clear and detailed description of the issue you are facing.
- Include any relevant error messages, code snippets, or screenshots.

Additionally, you can refer to the `official documentation`_ for additional
resources and troubleshooting guides.


Contribute
==========

Contributions are welcome!
If you would like to contribute, please follow the guidelines provided in the `Contribute`_
section of the official documentation.


License
=======

You can find the full text of the license in the `LICENSE`_ file.


Changelog
=========

The changelog section provides a summary of notable changes for each version of
SAF Templates. It helps you keep track of updates, bug
fixes, new features, and improvements made to the project over time.

To view the complete changelog, visit the project repository and navigate
to the `CHANGELOG`_ file. It provides a comprehensive list of changes
categorized by version, along with brief descriptions of each change.


.. _official documentation: https://saf.ansys.com/
.. _project repository: https://github.com/ansys/saf/
.. _prerequisites: https://saf.ansys.com/version/stable/getting_started/prerequisites/index.html
.. _Template gallery: https://saf.ansys.com/version/stable/user_guide/add_step.html#step-template-gallery
.. _Contribute: https://saf.ansys.com/version/stable/contribute/index.html
.. _LICENSE: https://github.com/ansys/saf/blob/main/packages/saf-templates/LICENSE
.. _CHANGELOG: https://github.com/ansys/saf/blob/main/packages/saf-templates/CHANGELOG.md

