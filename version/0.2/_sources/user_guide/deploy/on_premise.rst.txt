.. _deploy_on_premise:

On-premises deployment
########################

:enterprise-badge:`Enterprise Feature`

.. admonition:: Available to Ansys customers and Channel Partners
   :class: enterprise

   This feature is available to Ansys customers and Channel Partners.
   `Contact the PyAnsys team <mailto:pyansys-core@synopsys.com>`_ to request access.

On-premise deployment enables multi-user access to SAF-based solution applications within an
organization's infrastructure. Unlike the desktop deployment, which targets a single user on a
single machine, on-premise deployments provide centralized management, authentication, and
collaboration capabilities.

Three deployment flavors are available, each targeting a different level of complexity and scalability:

- **Single node deployment on Windows**: All services run natively on a single Windows machine as Windows services.
- **Distributed deployment powered by Docker Compose**: All services run as Docker containers on a single Linux machine.
- **Distributed deployment powered by K3s**: Services run on a lightweight Kubernetes cluster, enabling container orchestration and Helm-based management.

.. note::
   On-premise deployment is an enterprise feature. Contact your Ansys representative for access
   to the deployment packages and detailed deployment documentation.


.. _on-premise-single-node-windows:

Single-node deployment on Windows
==================================

The **Ansys App Portal Windows Services** package provides a turnkey deployment of the SAF platform
on a single Windows machine. All platform services—the Ansys App Portal, authentication (Keycloak),
authorization (OpenFGA), databases, and an application service—run natively as Windows services
behind an Nginx reverse proxy. This approach is well-suited for small teams or departmental
deployments where simplicity and minimal infrastructure are priorities.

Key capabilities:

- **Single installer**: A batch script installs and starts all services in one step.
- **Windows service lifecycle**: Services are managed through the Windows Services console (``services.msc``) or the ``sc`` command, with automatic startup on boot.
- **Integrated authentication**: Keycloak provides identity management with user registration and role-based access.
- **Fine-grained authorization**: OpenFGA enables project-level and application-level access control.
- **Reverse proxy**: Nginx exposes a single HTTPS port for all user traffic.
- **Ansys product integration**: Supports Ansys optiSLang 2025 R2 for simulation execution.

Target environment:

- Windows 11 (64-bit), minimum 32 GB RAM, minimum 16 logical cores, minimum 512 GB disk space.
- Single machine—no container runtime required.


.. _on-premise-docker-compose:

Distributed deployment using Docker Compose
==============================================

The **Ansys App Portal and Distributed Deployment Templates** platform provides a containerized
deployment of the SAF platform using Docker Compose. All services run as isolated containers on
a single Linux machine, making this approach ideal for production-grade departmental deployments
that require reproducibility, easy upgrades, and support for multiple solution application types.

Key capabilities:

- **Containerized architecture**: All services (portal, authentication, databases, reverse proxy, HPS, observability) run in Docker containers.
- **Multi-app support**: Deploy Ansys Fluent web apps, Ansys standalone web apps, Ansys optiSLang web apps, and Ansys ModelCenter web apps.
- **Profile-based activation**: Use Docker Compose profiles to enable only the services required for your deployment scenario.
- **TLS support**: Traefik reverse proxy provides HTTPS termination with configurable certificates.
- **HPC integration**: Built-in Ansys HPC Platform Services (HPS) for job scheduling and solver management.
- **Data services**: Optional integrated data management capabilities with S3-compatible blob storage.
- **Observability**: Built-in monitoring with metrics, logs, and traces.
- **Automated app deployment**: Upload ``.awa`` files through the portal for one-click application deployment.
- **Solver node separation**: Ansys products can be installed on a separate solver node for resource isolation.

Target environment:

- Linux Ubuntu 22.04 LTS or 24.04 LTS
- Cores - minimum 8 cores, recommended 12 cores
- RAM: minimum 32 GB, recommended: 64 GB
- Requires Docker Engine and Docker Compose 2.17.0 or later.


.. _on-premise-k3s:

Distributed deployment using K3s
======================================

The **K3s-based deployment** uses Helm charts to deploy the SAF platform on a lightweight
Kubernetes cluster. K3s is a certified Kubernetes distribution optimized for edge and
resource-constrained environments, making it suitable for on-premise deployments that require
container orchestration without the overhead of a full Kubernetes cluster.

Key capabilities:

- **Kubernetes-native**: Leverages standard Kubernetes resources (Deployments, Services, ConfigMaps, PersistentVolumeClaims, Ingress).
- **Helm-based management**: Install, upgrade, and roll back the platform using Helm charts.
- **Multi-app support**: Deploy Ansys Fluent web apps, Ansys standalone web apps, and Ansys optiSLang web apps.
- **HPC integration**: Built-in Ansys HPC Platform Services (HPS) for job scheduling and solver management.
- **Data services**: Optional integrated data management capabilities with S3-compatible blob storage.
- **Automated app deployment**: Upload ``.awa`` files through the portal for one-click application deployment.
- **Standard ingress**: Traefik ingress controller (bundled with K3s) routes external traffic to services.
- **External identity**: Integrates with external Keycloak instances for centralized identity management across environments.
- **Persistent storage**: Uses Kubernetes ``PersistentVolumeClaims`` for database and portal data.
- **GitOps compatible**: Helm values and chart versions can be tracked in version control for reproducible deployments.

Target environment:

- Linux Ubuntu 22.04 LTS or 24.04 LTS
- Cores - minimum 12 cores, recommended 16 cores
- RAM: minimum 32 GB, recommended: 64 GB
- Requires K3s, Helm 3.x, and ``kubectl``.


.. _on-premise-comparison:

Comparison matrix
=================

Use the following matrix to determine which on-premise deployment option best fits your needs:

.. list-table::
   :header-rows: 1
   :widths: 30 23 23 24

   * - Criteria
     - Single node (Windows)
     - Docker Compose (Linux)
     - K3s (Linux)
   * - **Target OS**
     - Windows 11
     - Linux Ubuntu 22.04/24.04
     - Linux Ubuntu 22.04/24.04
   * - **Infrastructure complexity**
     - Low
     - Medium
     - High
   * - **IT expertise required**
     - Windows system administration
     - Docker and Linux administration
     - Kubernetes, Helm, and Linux
   * - **Scalability**
     - Single machine only
     - Single machine only
     - Single machine only
   * - **High availability**
     - No
     - No
     - No
   * - **Supported app types**
     - optiSLang web apps
     - Fluent, standalone, optiSLang, ModelCenter
     - Fluent, standalone, optiSLang
   * - **Container runtime required**
     - No
     - Yes (Docker)
     - Yes (containerd via K3s)
   * - **Service management**
     - Windows Services (``sc``, ``services.msc``)
     - Docker Compose (``docker compose up/down``)
     - Helm and kubectl
   * - **TLS / HTTPS**
     - Self-signed via Nginx
     - Configurable via Traefik
     - Configurable via Ingress
   * - **Authentication**
     - Keycloak
     - Keycloak
     - External Keycloak
   * - **Authorization**
     - OpenFGA
     - OpenFGA
     - OpenFGA
   * - **HPC job submission**
     - No
     - Yes (HPS integrated)
     - Yes (HPS integrated)
   * - **Data services**
     - No
     - Yes (optional profile)
     - Yes (optional)
   * - **Observability**
     - Basic (log files)
     - Yes (metrics, logs, traces)
     - Yes (Kubernetes-native)
   * - **Automated app deployment**
     - No
     - Yes (``.awa`` upload)
     - Yes (``.awa`` upload)
   * - **Upgrade mechanism**
     - Reinstall package
     - Rebuild and restart containers
     - ``helm upgrade``
   * - **Rollback capability**
     - Manual
     - Manual (re-deploy previous images)
     - Built-in (``helm rollback``)
   * - **Best suited for**
     - Small teams, Windows-only environments
     - Departmental production deployments
     - Enterprise-scale, multi-team environments


Choose the right deployment
===============================

- **Choose Single node (Windows)** if your team works in a Windows-only environment, you need
  minimal infrastructure overhead, and your primary use case involves optiSLang web apps.

- **Choose Docker Compose (Linux)** if you need a production-grade deployment supporting multiple
  application types (Fluent, standalone, optiSLang, ModelCenter), integrated HPC job submission,
  and data services—all on a single Linux machine.

- **Choose K3s (Linux)** if you need Kubernetes-native management, GitOps-compatible
  deployments, and built-in rollback capabilities for enterprise-scale environments.
