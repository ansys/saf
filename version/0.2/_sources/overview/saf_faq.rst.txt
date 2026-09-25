.. _saf_faq:

SAF FAQ
########

This is a list of frequently asked questions about :program:`SAF`.

.. _faq-definition:

.. _faq-support:

Backend programming languages
=============================

:medium-bold:`What backend programming languages does SAF support?`
 SAF GLOW Engine, the backend engine of SAF, is a Python-based framework. By design, it only supports writing applications in Python.


.. _frontend-frameworks:

Frontend frameworks
-------------------

:medium-bold:`What frontend frameworks does SAF support?`
 An application's backend powered by GLOW is a RESTful API service, so it supports any UI framework that can invoke REST API calls.
 We recommend using `Plotly Dash <https://dash.plotly.com/>`_ for its simplicity, and we provide templates to scaffold an application using this technology.

:medium-bold:`Is there a plan to provide templates for Angular or React frontends instead of Dash?`
 No.

IronPython
-----------

:medium-bold:`Can SAF be called with IronPython?`
 No. IronPython is not compatible with SAF.

Operating systems
------------------

:medium-bold:`What operating systems does SAF support?`
 For OS and version details, see each package documentation (summary of the SAF components under the starting page).


Containerization
-----------------

:medium-bold:`Does SAF support containerization?`
 Yes, Docker files are provided as part of the templates.

Deployment
-----------

:medium-bold:`What types of deployment does SAF currently support?`
 A SAF-based application can be installed locally or deployed in a containerized manner. Server deployment can be either on-premises or in a private cloud.


:medium-bold:`Will SAF support cloud deployment?`
 It is already possible to deploy a SAF-based application in a private cloud on a single node. Multi-node deployment support is under development, enabling deployment either in an on-premises datacenter or in a private cloud.


.. _faq-features:

Concurrent projects
---------------------

:medium-bold:`In the same user session, can I launch multiple projects concurrently?`
 Yes.


Remote monitoring
------------------

:medium-bold:`Does SAF provide monitoring capabilities for simulation processes executed remotely?`
 SAF itself does not provide any built-in way to track the status of a simulation process with remote execution, but it can integrate with HPC job schedulers and monitoring tools.

Solution resume
---------------

:medium-bold:`Can I start a solve and then come back to it?`
 Yes. You may start a solve, exit the project, and then return to the project to check its progress.

 However, for desktop deployments, you must keep both the SAF Portal and the console from which you started the application open. Closing either of these shuts down the application, thus terminating the solve operation.


Unit handling
--------------

:medium-bold:`Does SAF have built-in unit handling for inputs and unit conversions?`
 No. We recommend using `pint <https://github.com/hgrecco/pint>`_, a third-party library for unit handling.


Data management
---------------

:medium-bold:`Can I use an external data management system with my SAF application?`
 Yes. SAF supports integration with external data management systems for both desktop and on-premises deployments.


.. _faq-plans:


Release timeline
-----------------

:medium-bold:`What is the release schedule for SAF?`
 SAF packages are provided in a Continuous Integration and Continuous Delivery (CI/CD) manner.







