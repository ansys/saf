# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
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

"""Sphinx documentation configuration file."""

from datetime import datetime
import os
from pathlib import Path
import shutil
import subprocess

from ansys_sphinx_theme import ansys_favicon, get_version_match
from sphinx.builders.latex import LaTeXBuilder  # pyright: ignore
from ansys.iam.oidc import __version__

THIS_PATH = Path(__file__).parent.resolve()

# ============================================================================
# Project information
# ============================================================================

project = "ansys-iam-oidc"
copyright = f"(c) {datetime.now().year} ANSYS, Inc. All rights reserved"  # noqa:DTZ005, A001
author = "ANSYS, Inc."
release = version = __version__
cname = os.getenv("CNAME")
switcher_version = get_version_match(__version__)

# ============================================================================
# General Sphinx configuration
# ============================================================================

source_suffix = ".rst"
master_doc = "index"
language = "en"
suppress_warnings = ["label.*", "toc.not_readable"]
todo_include_todos = False
numfig = True
numfig_secnum_depth = 1
numfig_format = {
    "figure": "Figure %s ",
    "table": "Table %s ",
    "code-block": "Code sample %s ",
}

exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
]

# ============================================================================
# Extensions
# ============================================================================

extensions = [
    "numpydoc",
    "sphinx_design",
    "sphinx.ext.intersphinx",
    "sphinx.ext.todo",
    "sphinx_copybutton",
    "sphinx_jinja",
    "sphinx.ext.mathjax",
    "ansys_sphinx_theme.extension.autoapi",
]

# ============================================================================
# Intersphinx
# ============================================================================

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "sphinx": ("https://www.sphinx-doc.org/en/master", None),
}

# ============================================================================
# Autodoc / Pydantic configuration
# ============================================================================

autodoc_mock_imports = ["ansys.platform", "opentelemetry"]

autodoc_pydantic_model_show_json = False
autodoc_pydantic_model_show_config = False
autodoc_pydantic_settings_show_json = False
autodoc_pydantic_model_show_validator_members = False
autodoc_pydantic_model_show_validator_summary = False

# ============================================================================
# Numpydoc configuration
# ============================================================================

numpydoc_use_plots = True
numpydoc_show_class_members = True
numpydoc_xref_param_type = True
numpydoc_validate = True
numpydoc_validation_checks = {
    "GL06",  # Found unknown section
    "GL07",  # Sections are in the wrong order.
    # "GL08",  # The object does not have a docstring
    "GL09",  # Deprecation warning should precede extended summary
    "GL10",  # reST directives {directives} must be followed by two colons
    "SS01",  # No summary found
    "SS02",  # Summary does not start with a capital letter
    "SS03",  # Summary does not end with a period
    "SS04",  # Summary contains heading whitespaces
    "SS05",  # Summary must start with infinitive verb, not third person
    "RT02",  # The first line of the Returns section should contain only the
    # type, unless multiple values are being returned"
}
numpydoc_validation_exclude = {
    "add_note",
    "isEnabledFor",
    "validate",
    "__cause__",
    "__context__",
    "model_dump_json",
    "model_dump",
    "model_copy",
}

# ============================================================================
# Copybutton configuration
# ============================================================================

# Exclude traditional Python prompts from the copied code
copybutton_prompt_text = r">>> ?|\.\.\. "
copybutton_prompt_is_regexp = True

# ============================================================================
# LaTeX configuration
# ============================================================================

LaTeXBuilder.supported_image_types = ["image/png", "image/pdf", "image/svg+xml"]

# ============================================================================
# Link check
# ============================================================================

linkcheck_ignore = [
    r"https://sphinxdocs.ansys.com/version/*",
]

# ============================================================================
# HTML output
# ============================================================================

html_theme = "ansys_sphinx_theme"
html_short_title = html_title = "IAM OIDC"
html_favicon = ansys_favicon
html_static_path = ["_static"]
templates_path = ["_templates"]
html_show_sourcelink = False
html_compact_lists = False

html_context = {
    "github_user": "ansys",
    "github_repo": "https://github.com/ansys/saf",
    "github_version": "main",
    "doc_path": "doc/source",
    "default_mode": "dark",
}

html_theme_options = {
    "github_url": f"https://github.com/ansys/saf/tree/main/packages/saf-iam-oidc",
    "contact_mail": "pyansys-core@synopsys.com",
    "use_edit_page_button": False,
    "logo": {
        "image_light": "_static/logos/endorsed-ansys-logos-gold-black-rgb.svg",
        "image_dark": "_static/logos/endorsed-ansys-logos-gold-white-rgb.svg",
    },
    "search_filters": {
        "User guide": [
            "user-guide/",
            "getting-started/",
            "index/",
        ],
        "Release notes": ["changelog"],
        "Examples": ["examples/"],
        "Contributing": ["contribute/"],
    },
    "show_breadcrumbs": True,
    "show_prev_next": False,
    "additional_breadcrumbs": [
        ("SAF", f"https://{cname}/version/stable/api/index.html"),
    ],
    "ansys_sphinx_theme_autoapi": {
        "project": project,
        "output": ".",
        "add_toctree_entry": False,
        "options": [
            "members",
            "undoc-members",
            "show-inheritance",
            "show-module-summary",
            "special-members",
            "imported-members",
        ],
    },
    # TODO: Remove once library is public
    "check_switcher": False,
}

html_theme_options["switcher"] = {
    "json_url": f"https://{cname}/version/stable/api/saf-iam-oidc/versions.json",
    "version_match": get_version_match(version),
}

# ============================================================================
# Jinja configuration
# ============================================================================

jinja_globals = {"version": version}

tox_command = shutil.which("tox")
tox_envs = []
if tox_command:
    tox_envs = subprocess.run(
        [tox_command, "list", "-d", "-q"],
        capture_output=True,
        text=True,
    ).stdout.splitlines()[1:]

jinja_contexts = {
    "toxenvs": {
        "envs": tox_envs,
    },
}

# ============================================================================
# Sphinx event hooks
# ============================================================================


def _rename_api_title(app, docname, source):
    """Replace the default autoapi module title with 'API reference'."""
    if docname == "ansys/iam/oidc/index":
        old_title = "The ``ansys.iam.oidc`` library"
        old_underline = "=" * len(old_title)
        new_title = "API reference"
        new_underline = "=" * len(new_title)
        source[0] = source[0].replace(
            f"{old_title}\n{old_underline}", f"{new_title}\n{new_underline}", 1
        )


def setup(app):
    """Connect Sphinx events."""
    app.connect("source-read", _rename_api_title)
