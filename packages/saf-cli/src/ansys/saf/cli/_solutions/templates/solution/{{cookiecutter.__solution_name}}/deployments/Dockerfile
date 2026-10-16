# === Base Stage ==================================================================================

FROM python:3.12-slim AS base

RUN apt update && apt install curl libx11-6 libglu1-mesa-dev libxrender1 libgl1 libglx-mesa0 xvfb iputils-ping tk libicu-dev -y
RUN pip install --upgrade pip && pip install uv==0.12.10

WORKDIR /app

COPY ../../pyproject.toml ../../uv.lock /app/
COPY README.md /app/

RUN mkdir -p /app/src/{{ cookiecutter.__solution_namespace_path }}/{{ cookiecutter.__solution_module_name }}
RUN touch /app/src/{{ cookiecutter.__solution_namespace_path }}/{{ cookiecutter.__solution_module_name }}/__init__.py

RUN uv sync --frozen --no-default-groups

RUN rm -rf /root/.cache/pip/* /dist /var/lib/apt/lists/*

# === API Stage ===================================================================================

FROM base AS solution_api

COPY ../../src/{{ cookiecutter.__solution_namespace_path }}/{{ cookiecutter.__solution_module_name }}/ /app/src/{{ cookiecutter.__solution_namespace_path }}/{{ cookiecutter.__solution_module_name }}/

# Directory required by pyHPS
RUN mkdir -p /.ansys/hps
RUN chmod -R 777 /.ansys/hps

ENTRYPOINT uv run --no-sync python -m uvicorn ansys.saf.glow.api:app --host $GLOW_API_HOST --port $GLOW_API_PORT --root-path $GLOW_API_PATH_PREFIX --workers ${GLOW_API_NUMBER_OF_WORKERS:-8}

# === UI Stage ====================================================================================

FROM base AS solution_ui

RUN uv sync --frozen --no-default-groups --group ui

COPY ../../src/{{ cookiecutter.__solution_namespace_path }}/{{ cookiecutter.__solution_module_name }}/ /app/src/{{ cookiecutter.__solution_namespace_path }}/{{ cookiecutter.__solution_module_name }}/

ENTRYPOINT uv run --no-sync python -m waitress --host $GLOW_UI_HOST --port $GLOW_UI_PORT --url-prefix $GLOW_UI_PATH_PREFIX ansys.saf.glow.ui:app
