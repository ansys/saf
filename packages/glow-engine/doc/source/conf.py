# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
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

"""Sphinx documentation configuration file."""

from datetime import datetime
import os
import shutil
import subprocess

from ansys_sphinx_theme import ansys_favicon, get_version_match

from ansys.saf.glow import __version__

# ============================================================================
# Project information
# ============================================================================

project = "ansys-saf-glow-engine"
copyright = f"(c) {datetime.now().year} ANSYS, Inc. All rights reserved"  # noqa: A001
author = "ANSYS, Inc."
release = version = __version__
cname = os.getenv("CNAME")
switcher_version = get_version_match(__version__)

# ============================================================================
# General Sphinx configuration
# ============================================================================

source_suffix = {".rst": "restructuredtext"}
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
    "links.rst",
    "substitutions.rst",
]

# ============================================================================
# Extensions
# ============================================================================

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "numpydoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.todo",
    "sphinx_copybutton",
    "sphinx_code_tabs",
    "sphinxcontrib.autodoc_pydantic",
    "sphinx_design",
    "sphinx_jinja",
]

# ============================================================================
# Intersphinx
# ============================================================================

intersphinx_mapping = {
    "python": ("https://docs.python.org/dev", None),
}

# ============================================================================
# Autodoc / Pydantic configuration
# ============================================================================

autodoc_mock_imports = [
    "ansys.platform",
    "opentelemetry",
    "ansys.aedt",
    "ansys.fluent",
    "ansys.mapdl",
    "ansys.mechanical",
    "ansys.optislang",
    "ansys.geometry",
    "ansys.visor",
]

autodoc_pydantic_model_show_json = False
autodoc_pydantic_model_show_config = False
autodoc_pydantic_settings_show_json = False
autodoc_pydantic_model_show_validator_members = False
autodoc_pydantic_model_show_validator_summary = False

# ============================================================================
# Numpydoc configuration
# ============================================================================

numpydoc_use_plots = True
numpydoc_show_class_members = False
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
    r"ResourceRequirements\.Meta$",  # class coming from ansys-hps-client
}

# ============================================================================
# Copybutton configuration
# ============================================================================

# Exclude traditional Python prompts from the copied code
copybutton_prompt_text = r">>> ?|\.\.\. "
copybutton_prompt_is_regexp = True

# ============================================================================
# Notfound extension
# ============================================================================

notfound_template = "404.rst"
notfound_urls_prefix = "/../"

# ============================================================================
# HTML output
# ============================================================================

html_theme = "ansys_sphinx_theme"
html_short_title = html_title = "SAF GLOW"
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
    "github_url": "https://github.com/ansys/saf/tree/main/packages/glow-engine",
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
    "check_switcher": False,
}

html_theme_options["switcher"] = {
    "json_url": f"https://{cname}/version/stable/api/glow-engine/versions.json",
    "version_match": get_version_match(version),
}

html_css_files = [
    "css/custom.css",
]

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
# External documentation links (rst_epilog substitutions)
# ============================================================================

saf_docs_base_url = "https://saf.ansys.com/version/stable"

rst_epilog = f"""
.. |saf-docs-asynchronous-execution-ref| replace:: the corresponding section
.. _saf-docs-asynchronous-execution-ref: {saf_docs_base_url}/user_guide/backend/workflow_definition/transaction_methods/asynchronous_execution.html
.. |saf-docs-check-method-execution-status-ref| replace:: the corresponding section
.. _saf-docs-check-method-execution-status-ref: {saf_docs_base_url}/user_guide/backend/workflow_definition/transaction_methods/asynchronous_execution.html#check-method-execution-status
.. |saf-docs-wait-for-long-running-ref| replace:: the corresponding section
.. _saf-docs-wait-for-long-running-ref: {saf_docs_base_url}/user_guide/backend/workflow_definition/transaction_methods/asynchronous_execution.html#wait-for-long-running-methods
.. |saf-docs-field-states-ref| replace:: the corresponding section
.. _saf-docs-field-states-ref: {saf_docs_base_url}/user_guide/backend/workflow_definition/transaction_methods/field_states.html#field-states-and-dependencies
.. |saf-docs-instance-management-ref| replace:: the corresponding section
.. _saf-docs-instance-management-ref: {saf_docs_base_url}/user_guide/backend/instance_management/index.html
.. |saf-docs-transaction-methods-ref| replace:: the corresponding section
.. _saf-docs-transaction-methods-ref: {saf_docs_base_url}/user_guide/backend/workflow_definition/transaction_methods/index.html
.. |saf-docs-user-guide-ref| replace:: the corresponding section
.. _saf-docs-user-guide-ref: {saf_docs_base_url}/user_guide/index.html
.. |saf-docs-solution-definition-ref| replace:: the corresponding section
.. _saf-docs-solution-definition-ref: {saf_docs_base_url}/user_guide/backend/workflow_definition/solution.html
.. |saf-docs-step-models-ref| replace:: the corresponding section
.. _saf-docs-step-models-ref: {saf_docs_base_url}/user_guide/backend/workflow_definition/steps.html
.. |saf-docs-uploading-field-during-async-execution-ref| replace:: the corresponding section
.. _saf-docs-uploading-field-during-async-execution-ref: {saf_docs_base_url}/user_guide/backend/workflow_definition/transaction_methods/asynchronous_execution.html#upload-a-field-during-asynchronous-execution
.. |saf-docs-create-product-instance-ref| replace:: the corresponding section
.. _saf-docs-create-product-instance-ref: {saf_docs_base_url}/user_guide/backend/instance_management/usage.html#create-a-product-instance
.. |saf-docs-access-use-product-instance-ref| replace:: the corresponding section
.. _saf-docs-access-use-product-instance-ref: {saf_docs_base_url}/user_guide/backend/instance_management/usage.html#use-a-running-product-instance
.. |saf-docs-hps-job-dependencies-ref| replace:: the corresponding section
.. _saf-docs-hps-job-dependencies-ref: {saf_docs_base_url}/user_guide/backend/job_submission/hps_job_submission.html#package-dependencies
.. |saf-docs-hps-job-specifiying-required-products-ref| replace:: the corresponding section
.. _saf-docs-hps-job-specifiying-required-products-ref: {saf_docs_base_url}/user_guide/backend/job_submission/hps_job_submission.html#specify-required-products
.. |saf-docs-hps-parametric-study-ref| replace:: the corresponding section
.. _saf-docs-hps-parametric-study-ref: {saf_docs_base_url}/user_guide/backend/job_submission/hps_job_submission.html#the-hps-parametric-study-api
.. |saf-docs-hps-function-ref| replace:: the corresponding section
.. _saf-docs-hps-function-ref: {saf_docs_base_url}/user_guide/backend/job_submission/hps_job_submission.html#functions-executed-in-hps
.. |saf-docs-hps-job-submit-single-ref| replace:: the corresponding section
.. _saf-docs-hps-job-submit-single-ref: {saf_docs_base_url}/user_guide/backend/job_submission/hps_job_submission.html#submit-a-single-job-to-hps
"""
