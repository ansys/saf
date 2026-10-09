# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from collections.abc import Generator
from importlib import invalidate_caches
from pathlib import Path
import platform
import shutil
import sys

import pytest

from ansys.saf.templates import get_plugin_path


@pytest.fixture
def database_path(mock_appdata: Path) -> Path:
    database_path = mock_appdata / "ansys" / "saf" / "cli" / "solution_db.json"
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return database_path


@pytest.fixture(scope="session")
def session_database_path(mock_session_appdata: Path) -> Path:
    database_path = mock_session_appdata / "ansys" / "saf" / "cli" / "solution_db.json"
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return database_path


def get_template_plugin_path(module_name: str) -> Path:
    if module_name == "templates":
        return get_plugin_path()
    return (
        Path(sys.prefix)
        / ("Lib" if platform.system() == "Windows" else "lib")
        / (
            "site-packages"
            if platform.system() == "Windows"
            else f"python{sys.version_info.major}.{sys.version_info.minor}/site-packages"
        )
        / "ansys"
        / "saf"
        / module_name
    )


def get_templates_toml_path(module_name: str) -> Path:
    return get_template_plugin_path(module_name) / "templates.toml"


def get_template_path(module_name: str, step_name: str) -> Path:
    return get_template_plugin_path(module_name) / "steps" / step_name


def _generate_plugin(module_name: str) -> tuple[Path, Path]:
    plugin_source_dir = Path(__file__).parent / "mocks" / "plugin"
    plugin_destination_dir = get_template_plugin_path(module_name)
    saf_cli_site_packages_dir = plugin_destination_dir.parents[2]
    if plugin_destination_dir.is_dir():
        shutil.rmtree(plugin_destination_dir)
    shutil.copytree(plugin_source_dir, plugin_destination_dir)
    plugin_distribution_dir = saf_cli_site_packages_dir / f"ansys_saf_{module_name}-0.1.dev0.dist-info"
    plugin_distribution_dir.mkdir(exist_ok=True)
    plugin_distribution_entry_point = plugin_distribution_dir / "entry_points.txt"
    plugin_distribution_entry_point.write_text(
        f"[ansys_saf_templates]\nplugin_path=ansys.saf.{module_name}:get_plugin_path\n",
    )
    invalidate_caches()
    return plugin_destination_dir, plugin_distribution_dir


def _clean_plugin(plugin_destination_dir: Path, plugin_distribution_dir: Path) -> None:
    if plugin_destination_dir.is_dir():
        shutil.rmtree(plugin_destination_dir)
    if plugin_distribution_dir.is_dir():
        shutil.rmtree(plugin_distribution_dir)


@pytest.fixture(scope="session", autouse=True)
def clean_custom_template_plugins() -> None:
    plugin_module_names = [
        "test_custom_templates",
        "test_custom_templates_empty_toml",
        "test_custom_templates_no_toml",
        "test_custom_templates_same_name_step",
        "test_custom_templates_invalid_template",
        "test_custom_templates_with_compatible_cli_constraint",
        "test_custom_templates_with_incompatible_cli_constraint",
        "test_custom_templates_with_invalid_cli_constraint",
        "test_custom_templates_fails_on_post_hook",
        "test_custom_templates_with_main_dep",
        "test_custom_templates_with_ui_dep",
        "test_custom_templates_with_glow_and_ui_deps",
        "test_custom_templates_with_glow_in_different_group",
        "test_custom_templates_with_new_dep_group",
        "test_custom_templates_with_invalid_dependency",
    ]
    for module_name in plugin_module_names:
        plugin_destination_dir = get_template_plugin_path(module_name)
        plugin_distribution_dir = (
            Path(sys.prefix)
            / ("Lib" if platform.system() == "Windows" else "lib")
            / (
                "site-packages"
                if platform.system() == "Windows"
                else f"python{sys.version_info.major}.{sys.version_info.minor}/site-packages"
            )
            / f"ansys_saf_{module_name}-0.1.dev0.dist-info"
        )
        _clean_plugin(plugin_destination_dir, plugin_distribution_dir)


@pytest.fixture
def install_custom_template_plugin() -> Generator[Path, None, None]:
    plugin_destination_dir, plugin_distribution_dir = _generate_plugin("test_custom_templates")
    yield plugin_destination_dir
    _clean_plugin(plugin_destination_dir, plugin_distribution_dir)


@pytest.fixture
def install_custom_template_plugin_empty_toml() -> Generator[Path, None, None]:
    plugin_destination_dir, plugin_distribution_dir = _generate_plugin("test_custom_templates_empty_toml")
    (plugin_destination_dir / "templates.toml").write_text("[templates]")
    yield plugin_destination_dir
    _clean_plugin(plugin_destination_dir, plugin_distribution_dir)


@pytest.fixture
def install_custom_template_plugin_no_toml() -> Generator[Path, None, None]:
    plugin_destination_dir, plugin_distribution_dir = _generate_plugin("test_custom_templates_no_toml")
    (plugin_destination_dir / "templates.toml").unlink()
    yield plugin_destination_dir
    _clean_plugin(plugin_destination_dir, plugin_distribution_dir)


@pytest.fixture
def install_custom_template_plugin_same_name_step() -> Generator[Path, None, None]:
    plugin_destination_dir, plugin_distribution_dir = _generate_plugin("test_custom_templates_same_name_step")
    templates_toml = plugin_destination_dir / "templates.toml"
    templates_toml.write_text(templates_toml.read_text().replace("second-step", "several-deps-step"))
    yield plugin_destination_dir
    _clean_plugin(plugin_destination_dir, plugin_distribution_dir)


@pytest.fixture
def install_custom_template_plugin_invalid_template() -> Generator[Path, None, None]:
    plugin_destination_dir, plugin_distribution_dir = _generate_plugin("test_custom_templates_invalid_template")
    templates_toml = plugin_destination_dir / "templates.toml"
    templates_toml.write_text(templates_toml.read_text().replace('type = "step"\n', ""))
    yield plugin_destination_dir
    _clean_plugin(plugin_destination_dir, plugin_distribution_dir)


@pytest.fixture
def install_custom_template_plugin_with_compatible_cli_constraint() -> Generator[Path, None, None]:
    plugin_destination_dir, plugin_distribution_dir = _generate_plugin(
        "test_custom_templates_with_compatible_cli_constraint",
    )
    templates_toml = plugin_destination_dir / "templates.toml"
    templates_toml_content = templates_toml.read_text()
    templates_toml_content += '\nsaf_cli_compatibility_range = ">=1.0.0"\n'
    templates_toml.write_text(templates_toml_content)
    yield plugin_destination_dir
    _clean_plugin(plugin_destination_dir, plugin_distribution_dir)


@pytest.fixture
def install_custom_template_plugin_with_incompatible_cli_constraint() -> Generator[Path, None, None]:
    plugin_destination_dir, plugin_distribution_dir = _generate_plugin(
        "test_custom_templates_with_incompatible_cli_constraint",
    )
    templates_toml = plugin_destination_dir / "templates.toml"
    templates_toml_content = templates_toml.read_text()
    templates_toml_content += '\nsaf_cli_compatibility_range = "<1.0.0"\n'
    templates_toml.write_text(templates_toml_content)
    yield plugin_destination_dir
    _clean_plugin(plugin_destination_dir, plugin_distribution_dir)


@pytest.fixture
def install_custom_template_plugin_with_invalid_cli_constraint() -> Generator[Path, None, None]:
    plugin_destination_dir, plugin_distribution_dir = _generate_plugin(
        "test_custom_templates_with_invalid_cli_constraint",
    )
    templates_toml = plugin_destination_dir / "templates.toml"
    templates_toml_content = templates_toml.read_text()
    templates_toml_content += '\nsaf_cli_compatibility_range = "invalid"\n'
    templates_toml.write_text(templates_toml_content)
    yield plugin_destination_dir
    _clean_plugin(plugin_destination_dir, plugin_distribution_dir)


@pytest.fixture
def install_custom_template_plugin_fails_on_post_hook() -> Generator[Path, None, None]:
    plugin_destination_dir, plugin_distribution_dir = _generate_plugin("test_custom_templates_fails_on_post_hook")
    post_hook_path = plugin_destination_dir / "steps" / "several_deps_step" / "hooks" / "post_gen_project.py"
    post_hook_content = post_hook_path.read_text()
    post_hook_content += "\n\nraise RuntimeError('simulated hook failure')\n"
    post_hook_path.write_text(post_hook_content)
    yield plugin_destination_dir
    _clean_plugin(plugin_destination_dir, plugin_distribution_dir)


@pytest.fixture
def install_custom_template_plugin_with_main_dep() -> Generator[Path, None, None]:
    plugin_destination_dir, plugin_distribution_dir = _generate_plugin("test_custom_templates_with_main_dep")
    templates_toml = plugin_destination_dir / "templates.toml"
    templates_content = templates_toml.read_text()
    templates_content += '\n\n[templates.second-step.dependencies.main]\nhumanize = "^4.15.0"\n'
    templates_toml.write_text(templates_content)
    yield plugin_destination_dir
    _clean_plugin(plugin_destination_dir, plugin_distribution_dir)


@pytest.fixture
def install_custom_template_plugin_with_ui_dep() -> Generator[Path, None, None]:
    plugin_destination_dir, plugin_distribution_dir = _generate_plugin("test_custom_templates_with_ui_dep")
    templates_toml = plugin_destination_dir / "templates.toml"
    templates_content = templates_toml.read_text()
    templates_content += '\n\n[templates.second-step.dependencies.ui]\nstreamlit = "^1.58.0"\n'
    templates_toml.write_text(templates_content)
    yield plugin_destination_dir
    _clean_plugin(plugin_destination_dir, plugin_distribution_dir)


@pytest.fixture
def install_custom_template_plugin_with_glow_and_ui_deps() -> Generator[Path, None, None]:
    plugin_destination_dir, plugin_distribution_dir = _generate_plugin("test_custom_templates_with_glow_and_ui_deps")
    templates_toml = plugin_destination_dir / "templates.toml"
    templates_content = templates_toml.read_text()
    templates_content += "\n\n[templates.second-step.dependencies.main]"
    sdk_dep_line = '\nansys-saf-sdk = {version = "^0.2.0", allow-prereleases=true, extras = ["core-hps"]}\n\n'
    templates_content += sdk_dep_line
    templates_content += '[templates.second-step.dependencies.ui]\nstreamlit = "^1.58.0"\n'
    templates_toml.write_text(templates_content)
    yield plugin_destination_dir
    _clean_plugin(plugin_destination_dir, plugin_distribution_dir)


@pytest.fixture
def install_custom_template_plugin_with_glow_in_different_group() -> Generator[Path, None, None]:
    plugin_destination_dir, plugin_distribution_dir = _generate_plugin(
        "test_custom_templates_with_glow_in_different_group",
    )
    templates_toml = plugin_destination_dir / "templates.toml"
    templates_content = templates_toml.read_text()
    templates_content += "\n\n[templates.second-step.dependencies.another_group]"
    sdk_dep_line = '\nansys-saf-sdk = {version = "^0.2.0", allow-prereleases=true, extras = ["core-hps"]}\n\n'
    templates_content += sdk_dep_line
    templates_content += '[templates.second-step.dependencies.ui]\nstreamlit = "^1.58.0"\n'
    templates_toml.write_text(templates_content)
    yield plugin_destination_dir
    _clean_plugin(plugin_destination_dir, plugin_distribution_dir)


@pytest.fixture
def install_custom_template_plugin_with_new_dep_group() -> Generator[Path, None, None]:
    plugin_destination_dir, plugin_distribution_dir = _generate_plugin("test_custom_templates_with_new_dep_group")
    templates_toml = plugin_destination_dir / "templates.toml"
    templates_content = templates_toml.read_text()
    templates_content += """\n\n[templates.second-step.dependencies.new_group]\nhumanize = '^4.15.0'"""
    templates_toml.write_text(templates_content)
    yield plugin_destination_dir
    _clean_plugin(plugin_destination_dir, plugin_distribution_dir)


@pytest.fixture
def install_custom_template_plugin_with_invalid_dependency() -> Generator[Path, None, None]:
    plugin_destination_dir, plugin_distribution_dir = _generate_plugin("test_custom_templates_with_invalid_dependency")
    templates_toml = plugin_destination_dir / "templates.toml"
    templates_content = templates_toml.read_text()
    templates_content += """\n\n[templates.second-step.dependencies.main]\nfake_package = '^0.-5.abc'"""
    templates_content = templates_content.replace("second-step", "third-step")
    templates_toml.write_text(templates_content)
    yield plugin_destination_dir
    _clean_plugin(plugin_destination_dir, plugin_distribution_dir)
