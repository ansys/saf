# Deployment Options

The solution template provides four different deployment options, each designed for specific use cases and environments. All deployments use Docker Compose for containerization.

## Prerequisites for Container Deployments

| Prerequisite | Description |
|--------------|-------------|
| WSL (Windows only) | [WSL](https://learn.microsoft.com/en-us/windows/wsl/install) |
| Virtualization | [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/) (requires a license) or [Docker Engine](https://docs.docker.com/engine/install/) (open-source) |
| Environment variables | Set `MACHINE_IP` with the IP address of your machine if you use Docker Desktop or the IP address of your WSL if you use WSL |

Find more information about each deployment in the [Server-to-server deployments section](https://saf-cli.docs.solutions.ansys.com/version/stable/user_guide/solution_s2s_deployment.html) of the saf-cli documentation.