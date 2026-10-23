# === Base Stage ==================================================================================

FROM python:3.12-slim AS base

RUN apt update && apt install curl libx11-6 libglu1-mesa-dev libxrender1 libgl1 libglx-mesa0 xvfb iputils-ping tk libicu-dev -y
RUN pip install --upgrade pip && pip install poetry==2.5.1

WORKDIR /app

COPY ../../pyproject.toml ../../poetry.lock /app/
COPY README.md /app/

RUN mkdir -p /app/src/{{ cookiecutter.__solution_namespace_path }}/{{ cookiecutter.__solution_module_name }}
RUN touch /app/src/{{ cookiecutter.__solution_namespace_path }}/{{ cookiecutter.__solution_module_name }}/__init__.py

RUN poetry install

RUN rm -rf /root/.cache/pip/* /dist /var/lib/apt/lists/*

# === API Stage ===================================================================================

FROM base AS solution_api

COPY ../../src/{{ cookiecutter.__solution_namespace_path }}/{{ cookiecutter.__solution_module_name }}/ /app/src/{{ cookiecutter.__solution_namespace_path }}/{{ cookiecutter.__solution_module_name }}/

# Directory required by pyHPS
RUN mkdir -p /.ansys/hps
RUN chmod -R 777 /.ansys/hps

ENTRYPOINT poetry run python -m uvicorn ansys.saf.glow.api:app --host $GLOW_API_HOST --port $GLOW_API_PORT --root-path $GLOW_API_PATH_PREFIX --workers ${GLOW_API_NUMBER_OF_WORKERS:-8}

# === UI Stage ====================================================================================

FROM base AS solution_ui

RUN poetry install --only ui
RUN poetry run pip install waitress

COPY ../../src/{{ cookiecutter.__solution_namespace_path }}/{{ cookiecutter.__solution_module_name }}/ /app/src/{{ cookiecutter.__solution_namespace_path }}/{{ cookiecutter.__solution_module_name }}/

ENTRYPOINT poetry run python -m waitress --host $GLOW_UI_HOST --port $GLOW_UI_PORT --url-prefix $GLOW_UI_PATH_PREFIX ansys.saf.glow.ui:app
