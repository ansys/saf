.. _saf:

Solution Application Framework
##############################

Simulation web application
==========================

Computer-Aided Engineering (CAE) software---such as Finite Element Analysis (FEA) solvers, Computational Fluid Dynamics (CFD) codes,
or specialized in-house solvers---are sophisticated tools built to resolve complex physics problems with high fidelity.
They are inherently designed for simulation experts who understand meshing strategies, boundary conditions, convergence criteria,
and result interpretation.

A :dfn:`simulation web application` is a browser-based (or desktop) application that wraps one or more of these solvers into a
purpose-built workflow, guiding users through the steps required to set up, execute, and analyze a simulation.
By packaging domain expertise into an accessible interface, simulation web applications open up these powerful solvers
to a broader audience---design engineers, project managers, or quality teams---without requiring deep solver knowledge.

A simulation web application can take many forms:

- A **single-physics, single-page app** that exposes one solver behind a streamlined interface.
- A **multi-step workflow** that chains CAD import, mesh generation, solver execution, and post-processing into a guided sequence.
- A **multi-domain application** that orchestrates several simulation products to tackle coupled engineering problems (for example, thermal-structural or fluid-structure interaction).

Regardless of complexity, the common denominator is that a simulation web application packages simulation expertise into an accessible,
repeatable experience---lowering the barrier to entry and reducing the risk of user error.

Beyond a simple frontend
-------------------------

A simulation web application is not merely a UI layer placed on top of a solver. Delivering real value requires a broad
ecosystem of capabilities working together:

Scalable architecture
 Stateless microservices for backend and frontend that can scale horizontally to handle increasing numbers of concurrent users and simulation jobs.

Browser-based 3D visualization
 Interactive rendering of CAD geometry, meshes, and simulation results directly in the browser, without requiring local software installations.

Job execution management
 Submitting, monitoring, and retrieving results from local or remote compute resources (HPC clusters, cloud instances).

Data extraction and post-processing
 Programmatic access to simulation outputs---scalar results, field data, convergence histories---for downstream analysis.

Reporting
 Automated generation of standardized reports (PDF, HTML) that capture inputs, results, and engineering conclusions.

Data persistence
 Saving and restoring application state so users can pause work and resume later without losing progress.

Authentication and access control
 Ensuring that sensitive simulation data and workflows are only accessible to authorized users.

Observability
 Logging, tracing, and metrics to monitor application health and diagnose issues in production.

Assembling and maintaining all of these capabilities from scratch for each new application is prohibitively expensive.
This is precisely the problem that SAF addresses---providing these building blocks as reusable, production-ready components.

.. note::

   The terminology around simulation web applications is diverse. All of the following terms are used interchangeably:

   - **Simulation web application**: the generic, technology-neutral term
   - **Solution application** (or simply *solution*): the term historically used within the simulation industry
   - **Vertical application**: emphasizes the domain-specific nature
   - **Guided workflow**: emphasizes the step-by-step user experience


A Python-centric framework for building simulation web applications
===================================================================

The :program:`Solution Application Framework (SAF)` is an open-source Python framework developed by Ansys Inc. and designed to facilitate the
development and deployment of simulation web applications. It provides a production-ready foundation---including a backend engine,
project scaffolding, data persistence, job execution, and deployment tooling---so that simulation engineers can focus on their
domain logic rather than on building and maintaining web infrastructure from scratch.

SAF bridges the gap between powerful simulation solvers and the end users who need accessible, guided interfaces to run them.
It transforms what would otherwise be a complex software engineering effort into a structured, repeatable process driven by
Python scripting and configuration.

Key differentiators
-------------------

The landscape for building simulation web applications includes general-purpose web frameworks, simulation-native commercial platforms,
and no-code tools. SAF occupies a distinct position by combining the following characteristics:

**Simulation-centric by design**
  Born from years of experience building and deploying simulation web applications across diverse industries and physics domains,
  SAF encodes hard-won lessons into its architecture. Every design decision---from the workflow step model to blob data management---is
  informed by the practical needs of CAE workflows rather than retrofitted from a generic web framework.

**Templated, production-ready applications**
  SAF provides scaffolded project templates that come with essential capabilities already in place: database integration,
  project structure, dependency management, containerization, and observability. This standardizes application development,
  removes boilerplate overhead, and gives developers a solid starting point from day one.

**Native Ansys simulation ecosystem integration**
  Out-of-the-box connectors to Ansys products---Mechanical, MAPDL, Fluent, Geometry Service, AEDT, and more---via
  their respective PyAnsys SDKs. Job submission to HPC clusters is enabled through HPC Platform Services (HPS),
  and enterprise data management is provided via dedicated storage services. These integrations are built into the
  framework rather than bolted on as afterthoughts.

**Desktop deployment capabilities**
  Unlike cloud-only frameworks, SAF delivers key capabilities for desktop distribution: self-contained distributable installer,
  code encryption and obfuscation to protect intellectual property, and offline installation support.

**Open, microservices architecture**
  SAF imposes no frontend lock-in. The backend exposes a RESTful API that any UI framework (Dash, React, Angular, or others)
  can consume. Third-party tools can be integrated via REST APIs. The templated architecture ensures that every application
  follows a well-defined, maintainable structure.

**Flexible deployment without code changes**
  A single application codebase can be deployed on desktop, on-premises servers, or cloud infrastructure---without modifying
  the source code. The deployment target is a configuration concern, not an architectural one.
