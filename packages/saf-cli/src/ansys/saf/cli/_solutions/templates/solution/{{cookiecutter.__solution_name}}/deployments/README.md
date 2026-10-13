# Deployment Options

The solution template provides several deployment options, each designed for specific use cases and environments. All deployments use Docker Compose for containerization.

| Deployment | Builds images locally? | Notes |
|------------|-----------------------|-------|
| `standalone/` | Yes | Single-host deployment; builds `solution_api` and `solution_ui` from `Dockerfile`. |
| `standalone-with-hps/` | Yes | Same as `standalone/` plus HPS integration. |
| `distributed-deployment-template/` | Yes | Multi-host deployment behind Traefik. |
| `external/` | **No** | Consumes pre-built images already present in the local Docker registry. Intended for environments without access to the private PyPI source used to build the images. See below. |

## External deployment

The `external/` recipe does not build any image. It expects the following images to be already loaded in the local Docker registry:

- `<APP_NAME>-api:<APP_IMAGE_VERSION>`
- `<APP_NAME>-ui:<APP_IMAGE_VERSION>` (only when a UI framework is enabled)

`APP_NAME` and `APP_IMAGE_VERSION` are defined in [`external/.env`](./external/.env).

Images are produced by the `build solution images` GitHub Actions workflow (`.github/workflows/build-image.yml`), which can be triggered manually via *Run workflow* on the Actions tab (with a custom `image_tag`) and also runs as part of the `build and release` workflow (with the default `main` tag). The workflow builds the images on a GitHub runner and publishes a single tar file as a workflow artifact. To deploy:

```bash
# 1. Download the artifact from the workflow run and extract the tar file.
docker load -i <APP_NAME>-images-<tag>.tar

# 2. Deploy.
cd deployments/external
docker compose up -d
```

## Prerequisites for Container Deployments

| Prerequisite | Description |
|--------------|-------------|
| WSL (Windows only) | [WSL](https://learn.microsoft.com/en-us/windows/wsl/install) |
| Virtualization | [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/) (requires a license) or [Docker Engine](https://docs.docker.com/engine/install/) (open-source) |
| Environment variables | Set `MACHINE_IP` with the IP address of your machine if you use Docker Desktop or the IP address of your WSL if you use WSL |

Find more information about each deployment in the [Server-to-server deployments section](https://saf-cli.docs.solutions.ansys.com/version/stable/user_guide/solution_s2s_deployment.html) of the saf-cli documentation.