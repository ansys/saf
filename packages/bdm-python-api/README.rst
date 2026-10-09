##############################
Blob Management API for Python
##############################

|python| |pypi| |GH-CI| |codecov| |Apache| |ruff|

.. |python| image:: https://img.shields.io/pypi/pyversions/ansys-bdm-api?logo=python&logoColor=white&label=Python
   :target: https://pypi.org/project/ansys-bdm-api/
   :alt: Python

.. |pypi| image:: https://img.shields.io/pypi/v/ansys-bdm-api.svg?logo=pypi&logoColor=white&label=PyPI
   :target: https://pypi.org/project/ansys-bdm-api/
   :alt: PyPI

.. |GH-CI| image:: https://img.shields.io/github/actions/workflow/status/ansys/saf/ci_cd_pr.yml?branch=main&label=CI-CD&logo=github
   :target: https://github.com/ansys/saf/actions/workflows/ci_cd_pr.yml?query=branch%3Amain
   :alt: GH-CI

.. |codecov| image:: https://img.shields.io/codecov/c/github/ansys/bdm-python-api
   :target: https://app.codecov.io/gh/ansys/bdm-python-api
   :alt: Codecov

.. |Apache| image:: https://img.shields.io/badge/License-Apache2.0-white.svg?labelColor=black
   :target: https://www.apache.org/licenses/
   :alt: Apache

.. |ruff| image:: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
   :target: https://github.com/astral-sh/ruff
   :alt: Ruff


Overview
========

Blob Data Management (BDM) Python API is a way to manage files and directories through
abstract references instead of direct file-system paths. In SAF GLOW, BDM is a
shared technology component that helps applications work with engineering data
in a scalable and cloud-ready way across different runtime environments.

The ``ansys-bdm-api`` package provides the Python interfaces and models for
working with BDM services. It is built around concepts such as
``EntityHandle``, which references a file or directory through metadata, and
``Storage Scopes``, which define where data lives and how it is transferred or
realized when needed.

This approach helps reduce unnecessary file copying, improves performance
through caching, and makes workflows more portable across Windows, Linux,
cloud, and on-premises environments. It also supports safer and more
consistent handling of large engineering datasets and directory structures.


Installation
============

Ensure you have all the necessary `prerequisites`_.

To install the Blob Management API for Python, run:

.. code-block:: bash

   pip install ansys-bdm-api


Documentation
=============

Visit the `official documentation`_ for detailed information on how to use the Blob Management API for Python.
Check the `API reference`_ for a complete list of classes, methods, and usage examples.


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
Blob Management API for Python. It helps you keep track of updates, bug
fixes, new features, and improvements made to the project over time.

To view the complete changelog, visit the project repository and navigate
to the `CHANGELOG`_ file. It provides a comprehensive list of changes
categorized by version, along with brief descriptions of each change.


.. _official documentation: https://saf.ansys.com/
.. _project repository: https://github.com/ansys/saf/
.. _prerequisites: https://saf.ansys.com/version/stable/getting_started/prerequisites/index.html
.. _API reference: https://saf.ansys.com/version/stable/api/bdm-python-api/index.html
.. _Contribute: https://saf.ansys.com/version/stable/contribute/index.html
.. _LICENSE: https://github.com/ansys/saf/blob/main/packages/bdm-python-api/LICENSE
.. _CHANGELOG: https://github.com/ansys/saf/blob/main/packages/bdm-python-api/CHANGELOG.md