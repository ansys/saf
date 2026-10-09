#########
IAM OIDC
#########

|python| |pypi| |GH-CI| |codecov| |Apache| |ruff|

.. |python| image:: https://img.shields.io/pypi/pyversions/ansys-iam-oidc?logo=python&logoColor=white&label=Python
   :target: https://pypi.org/project/ansys-iam-oidc/
   :alt: Python

.. |pypi| image:: https://img.shields.io/pypi/v/ansys-iam-oidc.svg?logo=pypi&logoColor=white&label=PyPI
   :target: https://pypi.org/project/ansys-iam-oidc/
   :alt: PyPI

.. |codecov| image:: https://img.shields.io/codecov/c/github/ansys/ansys-iam-oidc
   :target: https://app.codecov.io/gh/ansys/ansys-iam-oidc
   :alt: Codecov

.. |GH-CI| image:: https://img.shields.io/github/actions/workflow/status/ansys/saf/ci_cd_pr.yml?branch=main&label=CI-CD&logo=github
   :target: https://github.com/ansys/saf/actions/workflows/ci_cd_pr.yml?query=branch%3Amain
   :alt: GH-CI

.. |Apache| image:: https://img.shields.io/badge/License-Apache2.0-white.svg?labelColor=black
   :target: https://www.apache.org/licenses/
   :alt: Apache

.. |ruff| image:: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
   :target: https://github.com/astral-sh/ruff
   :alt: Ruff


Overview
========

The ``ansys-iam-oidc`` package provides Python utilities for adding OAuth 2.0
and OpenID Connect (OIDC) authentication to SAF applications. It simplifies
the integration of secure identity flows so that developers can protect APIs,
validate access tokens, and retrieve user information without implementing the
underlying protocol details themselves.

Key capabilities include:

- **Token validation**: Verify access-token signatures, expiration, and audience
  claims against an OIDC provider's public keys.
- **User information retrieval**: Obtain standard OIDC user-profile claims
  either from the token itself or by querying the provider's ``userinfo``
  endpoint.
- **FastAPI integration**: Ready-to-use dependency classes for protecting
  FastAPI routes, including support for HTTP requests and WebSocket connections.
- **Flexible client modes**: Support for synchronous and asynchronous workflows
  through ``OidcClient`` and ``AsyncOidcClient``.
- **Standard OIDC flows**: Foundation for authorization-code with PKCE, client
  credentials, device-code, token introspection, token revocation, and token
  exchange.

By handling discovery, key retrieval, and claim validation internally, the
package allows developers to focus on application logic while relying on a
consistent and tested authentication layer.


Installation
============

Ensure you have all the necessary `prerequisites`_.

To install IAM OIDC, run:

.. code-block:: bash

   pip install ansys-iam-oidc


Documentation
=============

Visit the `official documentation`_ for detailed information on how to use IAM OIDC.
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
SAF IAM OIDC for Python. It helps you keep track of updates, bug fixes, new
features, and improvements made to the project over time.

To view the complete changelog, visit the project repository and navigate
to the `CHANGELOG`_ file. It provides a comprehensive list of changes
categorized by version, along with brief descriptions of each change.


.. _prerequisites: https://saf.ansys.com/version/stable/getting_started/prerequisites/index.html
.. _official documentation: https://saf.ansys.com/
.. _project repository: https://github.com/ansys/saf/
.. _API reference: https://saf.ansys.com/version/stable/api/saf-iam-oidc/index.html
.. _Contribute: https://saf.ansys.com/version/stable/contribute/index.html
.. _LICENSE: https://github.com/ansys/saf/blob/main/packages/saf-iam-oidc/LICENSE
.. _CHANGELOG: https://github.com/ansys/saf/blob/main/packages/saf-iam-oidc/CHANGELOG.md