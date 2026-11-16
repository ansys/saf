Default testing solution, with shared files for Poetry and UV. It should include:
- method_assets for testing encryption.
- build_assets for testing local dependencies.
    - ansys_solutions_custom_package_for_installer_test: dependency that has a subdependency that is defined by a wheel URL.
    - custom-package-for-test-2: minimal local wheel package with different wheel files depending on OS.
- tqdm and pooch dependencies for testing custom Desktop and UI dependencies.
- doc/source for testing documentation build.
- .env file for testing support for env files

`pyproject.poetry.toml` and `poetry.lock` describe the Poetry variant;
`pyproject.uv.toml` and `uv.lock` describe the UV variant. Test fixtures copy only
the selected configuration (as `pyproject.toml`) and lock into a temporary directory.