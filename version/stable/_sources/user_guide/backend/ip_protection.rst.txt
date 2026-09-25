.. _ip_protection:


IP protection
#############

:enterprise-badge:`Enterprise Feature`



.. admonition:: Available to Ansys customers and Channel Partners
   :class: enterprise

   This feature is available to Ansys customers and Channel Partners.
   `Contact the PyAnsys team <mailto:pyansys-core@synopsys.com>`_ to request access.

When you distribute a SAF-based solution, your business logic—algorithms, transaction method
scripts, and data files—needs to remain protected. SAF provides two complementary approaches
to IP protection depending on the deployment model.


Desktop deployment
==================

When a solution is packaged as a standalone desktop installer using ``saf build``, the application
binary is physically distributed to end-user machines. Without protection, all Python source files
and data assets would be accessible on the local file system.

SAF addresses this with **build-time encryption**:

1. **Declare protected assets**—list the scripts and data files to protect in an ``obfuscate.txt``
   manifest inside the ``method_assets/`` directory of your solution.
2. **Build with encryption**—run ``saf build --encrypt``. The SAF CLI encrypts every listed asset
   before packaging the installer.
3. **Distribute safely**—the resulting installer bundles only encrypted artifacts.
   No plain-text source code ships with the package.
4. **Transparent runtime**—at runtime, assets are decrypted **in-memory** on demand.
   Decrypted content is never written to disk. Your transaction methods execute exactly as they do
   in development, with no code changes required.

For build command details, see the |saf-cli-doc-ref| and the |installer-doc-ref|.


On-premises deployment
========================

In an on-premises deployment the solution runs as a web service on infrastructure managed by the
customer's IT team. The application source code is deployed to a server and is never distributed to
end-user machines—users only interact with the solution through a web browser.

In this model, IP protection is enforced at the **infrastructure level** rather than through file
encryption:

- **Server-side execution**—all business logic runs on the server. End users send inputs and
  receive outputs through the REST API; they never have access to the file system where the
  source code resides.
- **Access controls**—standard infrastructure security (file system permissions, network
  segmentation, containerisation) restricts access to the deployment environment.
- **Authentication and authorisation**—SAF integrates with Keycloak (OIDC) and OpenFGA to ensure
  that only authorised users can interact with the solution. See :ref:`authentication_and_authorization`.
- **No encryption required**—because the code is not distributed, there is no need to encrypt
  source files. The application runs from plain Python modules on the server.


