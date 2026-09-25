# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""Sphinx documentation configuration file."""

import os
from datetime import datetime
from pathlib import Path
import re

import toml
from ansys_sphinx_theme import ansys_favicon, get_version_match  # pyright: ignore[reportMissingImports]
from docutils.parsers.rst import Directive
from docutils import nodes


BRANCH = "main"
ORGANIZATION_NAME = "ansys"
DOC_PATH = "doc/source"
CNAME = "saf.ansys.com"
REPOSITORY_URL = "github.com/ansys/saf"

configuration_file = None
root_path = Path(__file__).resolve().parents[2]
saf_sdk_path = root_path / "packages" / "saf-sdk"
configuration_file = saf_sdk_path / "pyproject.toml"

if not configuration_file.exists():
    raise FileNotFoundError(f"No configuration file found at {configuration_file}.")

configuration = toml.load(configuration_file)

project_name = configuration["project"]["name"]
version = configuration["project"]["version"]
copyright = f"©{datetime.now().year} ANSYS, Inc. All rights reserved."
author = "ANSYS Inc."


extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "numpydoc",
    "nbsphinx",
    "sphinx.ext.intersphinx",
    "sphinx_copybutton",
    "sphinx_code_tabs",
    "sphinx.ext.todo",
    "sphinx_design",
    "sphinx_toolbox.collapse",
    "sphinx.ext.graphviz",
    "sphinxcontrib.mermaid",
    "sphinx_gallery.gen_gallery",
]

# ---------------------------------------------------------------------------
# Sphinx-gallery: build package example galleries directly into the central
# doc tree. Each entry pairs a package's example scripts (``examples_dirs``)
# with the generated gallery location under ``doc/source`` (``gallery_dirs``).
# ``plot_gallery=False``/``image_scrapers=()`` because Dash apps can't run
# headlessly; sphinx-gallery still parses the ``# %%`` text blocks.
# Add one examples_dirs/gallery_dirs pair per package as more galleries move here.
# ---------------------------------------------------------------------------
sphinx_gallery_conf = {
    "examples_dirs": [
        "../../packages/dash-super-components/examples/gallery_apps",
    ],
    "gallery_dirs": [
        "examples/dash_super_components_examples",
    ],
    "download_all_examples": False,
    "plot_gallery": False,
    "within_subsection_order": "FileNameSortKey",
    "image_scrapers": (),
    "remove_config_comments": True,
}

# ---------------------------------------------------------------------------
# Intersphinx: component API references
# Each entry links the central doc to a component's published API reference.
# URL pattern: https://<component-cname>/version/stable/objects.inv
# ---------------------------------------------------------------------------
intersphinx_mapping = {
    "python": ("https://docs.python.org/dev", None),
    "glow": (
        f"https://{os.getenv('GLOW_DOC_CNAME', 'glow-engine.docs.solutions.ansys.com')}/version/stable",
        None,
    ),
    "saf_cli": (
        f"https://{os.getenv('SAF_CLI_DOC_CNAME', 'saf-cli.docs.solutions.ansys.com')}/version/stable",
        None,
    ),
    "bdm_api": ("https://bdm-python-api.docs.solutions.ansys.com/version/stable", None),
    "bdm_shared_volume": (
        "https://bdm-python-shared-volume.docs.solutions.ansys.com/version/stable",
        None,
    ),
    "iam_oidc": (
        "https://ansys-iam-oidc.docs.solutions.ansys.com/version/stable",
        None,
    ),
    "product_config": (
        "https://saf-product-configuration.docs.solutions.ansys.com/version/stable",
        None,
    ),
    "product_manager": (
        "https://saf-product-manager.docs.solutions.ansys.com/version/stable",
        None,
    ),
    "orchestrator": (
        "https://saf-desktop-orchestrator.docs.solutions.ansys.com/version/stable",
        None,
    ),
    "installer": (
        "https://saf-desktop-installer.docs.solutions.ansys.com/version/stable",
        None,
    ),
    "testing": (
        "https://saf-sdk-testing.docs.solutions.ansys.com/version/stable",
        None,
    ),
    "templates": (
        "https://saf-templates.docs.solutions.ansys.com/version/stable",
        None,
    ),
    # "super_components": placeholder removed — dash-super-components now lives in the saf metapackage;
    # cross-reference it via the merged api/dash-super-components path instead of a standalone domain.
    "translation": (
        "https://translation-utilities.docs.solutions.ansys.com/version/stable",
        None,
    ),
    # "minerva": placeholder removed — same URL as iam_oidc; update when Minerva client publishes its own docs
}

# Allow local / offline builds to skip intersphinx fetching entirely.
if os.getenv("DISABLE_INTERSPHINX", "false").lower() == "true":
    intersphinx_mapping = {}

html_favicon = ansys_favicon
notfound_template = "404.rst"
notfound_urls_prefix = "/../"
html_static_path = ["_static"]
html_css_files = [
    "css/custom.css",
    "css/carousel.css",
    "css/landing_page_banner.css",
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.1.1/css/all.min.css",
    "https://fonts.googleapis.com/icon?family=Material+Icons",
]
html_js_files = [
    "js/sidebar-always-expanded.js",
    "js/sdI_button_ref_tooltips.js",
    "js/primary-sidebar-sticky-offset.js",
]
templates_path = ["_templates"]
source_suffix = ".rst"
master_doc = "index"
language = "en"
exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    "links.rst",
    "substitutions.rst",
    # nbsphinx (loaded for project notebooks) claims .ipynb as a source suffix, which collides
    # with the download notebooks that sphinx-gallery generates alongside each example's .rst page.
    "examples/dash_super_components_examples/**/*.ipynb",
    # Legacy user_guide content — will be cleaned up during content migration (Tasks 7-12)
    "cheat_sheets/**",
    "user_guide/create_solution/**",
    "user_guide/data_management_systems/**",
    "user_guide/debugging/**",
    "user_guide/documentation/**",
    "user_guide/execution_configuration/**",
    "user_guide/migration_guides/**",
    "user_guide/solution_backend/**",
    "user_guide/solution_frontend/**",
    "user_guide/solution_run/**",
    "user_guide/using_ansys_products/**",
    "deployment/on_premises.rst",
    "deployment/desktop/obfuscate_solution.rst",
    "about/**",
    "toc_tree.rst",
    "blog/recent_posts.rst",
]

todo_include_todos = os.environ.get("SAF_DOCS_INCLUDE_TODOS", "0") == "1"

copybutton_prompt_text = r">>> ?|\.\.\. "
copybutton_prompt_is_regexp = True

html_short_title = html_title = "SAF Doc"
html_theme = "ansys_sphinx_theme"
html_theme_options = {
    "logo": {
        "image_light": "_static/logos/endorsed-ansys-logos-gold-black-rgb.svg",
        "image_dark": "_static/logos/endorsed-ansys-logos-gold-white-rgb.svg",
    },
    "show_prev_next": False,
    "show_breadcrumbs": True,
    "collapse_navigation": True,
    "show_page_toc": True,
    "show_source_button": False,
    "use_edit_page_button": False,
    "check_switcher": False,
    "header_links_before_dropdown": 8,
    # "additional_breadcrumbs": [
    #     ("PyAnsys", "https://docs.pyansys.com/"),
    # ],
    # To hide the secondary (right) sidebar container on a page, set it to an empty list [].
    # The theme automatically hides the container when no items are present.
    "secondary_sidebar_items": {
        "**": ["page-toc", "sourcelink"],
        "index": [],
        "overview/index": [],
        "getting_started/index": [],
        "getting_started/prerequisites/index": [],
        "getting_started/tutorial/index": [],
        "getting_started/tutorial/development/index": [],
        "user_guide/index": [],
        "user_guide/scaffolding/index": [],
        "user_guide/run_locally/index": [],
        "user_guide/debug/index": [],
        "user_guide/test/index": [],
        "user_guide/troubleshooting/index": [],
        "user_guide/package/index": [],
        "user_guide/deploy/index": [],
        "user_guide/backend/index": [],
        "user_guide/backend/workflow_definition/index": [],
        "user_guide/backend/workflow_definition/transaction_methods/index": [],
        "user_guide/backend/blob_management/index": [],
        "user_guide/backend/job_submission/index": [],
        "user_guide/backend/data_management/index": [],
        "user_guide/backend/authn_authz/index": [],
        "user_guide/backend/apis/index": [],
        "user_guide/frontend/index": [],
        "user_guide/frontend/dash/index": [],
        "user_guide/frontend/dash/getting_started_with_dash": [],
        "user_guide/frontend/dash/dash_libraries/index": [],
        "user_guide/frontend/dash/dash_templates/index": [],
        "user_guide/best_practices/index": [],
        "user_guide/migration/index": [],
        "blog/index": [],
        "release_notes/index": [],
        "api/index": [],
    },
}


html_sidebars = {
    "index": [],
}

if str(os.getenv("DISABLE_GITHUB_URL_LINK")).lower() != "true":
    html_theme_options["github_url"] = f"https://{REPOSITORY_URL}"

if str(os.getenv("DISABLE_VERSION_SWITCHER")).lower() != "true":
    cname = os.getenv("CNAME", CNAME)
    html_theme_options["switcher"] = {
        "json_url": f"https://{cname}/versions.json",
        "version_match": get_version_match(version),
    }

html_context = {
    "display_github": False,
    "github_user": ORGANIZATION_NAME,
    "github_repo": REPOSITORY_URL,
    "github_version": BRANCH,
    "doc_path": DOC_PATH,
    "version": version,
    "default_mode": "dark",
}
html_show_sourcelink = False
html_compact_lists = False
htmlhelp_basename = "safdocs"

latex_elements = {}
latex_documents = [
    (master_doc, f"SAF-Docs-{version}.tex", "SAF Documentation", author, "manual"),
]
man_pages = [(master_doc, "SAF Documentation", "SAF Documentation", [author], 1)]
texinfo_documents = [
    (
        master_doc,
        "SAF Documentation",
        "SAF Documentation",
        author,
        "SAF",
        "Engineering Software",
    ),
]


# ---------------------------------------------------------------------------
# Custom admonitions (carried over from solutions-developer-guide)
# ---------------------------------------------------------------------------
class TheoryAdmonition(Directive):
    has_content = True

    def run(self):
        self.assert_has_content()
        text = "\n".join(self.content)
        node = nodes.admonition(text, classes=["custom-admonition", "theory"])
        node += nodes.title(text="Theory")
        self.state.nested_parse(self.content, self.content_offset, node)
        return [node]


class PracticeAdmonition(Directive):
    has_content = True

    def run(self):
        self.assert_has_content()
        text = "\n".join(self.content)
        node = nodes.admonition(text, classes=["custom-admonition", "practice"])
        node += nodes.title(text="Practice")
        self.state.nested_parse(self.content, self.content_offset, node)
        return [node]


class ExampleAdmonition(Directive):
    has_content = True

    def run(self):
        self.assert_has_content()
        text = "\n".join(self.content)
        node = nodes.admonition(text, classes=["custom-admonition", "example"])
        node += nodes.title(text="Example")
        self.state.nested_parse(self.content, self.content_offset, node)
        return [node]


class KeyConceptAdmonition(Directive):
    """Highlight a fundamental SAF concept.

    Takes an optional argument used as the concept name, for example::

        .. key-concept:: Transaction

            A transaction method is the only place where step fields are read or written.
    """

    has_content = True
    required_arguments = 0
    optional_arguments = 1
    final_argument_whitespace = True

    def run(self):
        self.assert_has_content()
        text = "\n".join(self.content)
        node = nodes.admonition(text, classes=["custom-admonition", "key-concept"])
        title = "Key concept"
        if self.arguments:
            title = f"{title} — {self.arguments[0]}"
        # Parse the title as inline reStructuredText so literals such as
        # ``@transaction`` render as code rather than raw backticks.
        title_nodes, messages = self.state.inline_text(title, self.lineno)
        node += nodes.title(title, "", *title_nodes)
        node += messages
        self.state.nested_parse(self.content, self.content_offset, node)
        return [node]


class BestPracticeAdmonition(Directive):
    """Highlight a recommended practice rather than a framework concept.

    Takes an optional argument used as the practice name, for example::

        .. best-practice:: Test on a clean machine

            An installer tested only on your workstation proves nothing.
    """

    has_content = True
    required_arguments = 0
    optional_arguments = 1
    final_argument_whitespace = True

    def run(self):
        self.assert_has_content()
        text = "\n".join(self.content)
        node = nodes.admonition(text, classes=["custom-admonition", "best-practice"])
        title = "Best practice"
        if self.arguments:
            title = f"{title} — {self.arguments[0]}"
        # Parse the title as inline reStructuredText so literals such as
        # ``saf build`` render as code rather than raw backticks.
        title_nodes, messages = self.state.inline_text(title, self.lineno)
        node += nodes.title(title, "", *title_nodes)
        node += messages
        self.state.nested_parse(self.content, self.content_offset, node)
        return [node]


def add_target_blank_to_external_links(app, doctree, docname):
    for node in doctree.traverse(nodes.reference):
        uri = node.get("refuri", "")
        if (
            uri.startswith("http")
            and "solutions.ansys.com" not in uri
            and "localhost" not in uri
        ):
            node["target"] = "_blank"
            node["rel"] = "noopener noreferrer"


def process_substitutions_in_directives(app, docname, source):
    if source:
        content = source[0]
        pattern = r"(:link:\s+)(\|[^|]+\|_)"

        def replace_substitution(match):
            prefix = match.group(1)
            sub_name = match.group(2)[1:-2]
            if sub_name in SUBSTITUTION_MAPPING:
                sub_data = SUBSTITUTION_MAPPING[sub_name]
                if isinstance(sub_data, dict) and "url" in sub_data:
                    return prefix + sub_data["url"]
                return prefix + str(sub_data)
            return match.group(0)

        source[0] = re.sub(pattern, replace_substitution, content)


# Sphinx-gallery generates examples/dash_super_components_examples/index.rst from the shared
# README at packages/dash-super-components/examples/gallery_apps/README.rst. That README is titled
# "Examples" because it is also used to generate the package's own standalone doc site, where
# "Examples" is the correct top-level title. In the central doc site, this page is nested under the
# broader "Examples" section, so retitle only this generated copy after sphinx-gallery writes it.
GALLERY_INDEX_DOCNAME = "examples/dash_super_components_examples/index"
GALLERY_INDEX_TITLE = "Dash Super Components"


def retitle_generated_gallery_index(app, docname, source):
    if docname != GALLERY_INDEX_DOCNAME or not source:
        return
    content = source[0]
    match = re.search(r"^Examples\n(#+)\n", content, re.MULTILINE)
    if not match:
        return
    underline = match.group(1)
    if len(underline) < len(GALLERY_INDEX_TITLE):
        underline = "#" * len(GALLERY_INDEX_TITLE)
    replacement = f"{GALLERY_INDEX_TITLE}\n{underline}\n"
    source[0] = content[: match.start()] + replacement + content[match.end() :]


def build_rst_epilog():
    lines = []
    for sub_name, sub_data in SUBSTITUTION_MAPPING.items():
        if sub_name == "VERSION":
            lines.append(f".. |{sub_name}| replace:: {sub_data}")
        else:
            lines.append(f".. |{sub_name}| replace:: {sub_data['text']}")
            lines.append(f".. _{sub_name}: {sub_data['url']}")
            lines.append("")
    return "\n".join(lines)


def setup(app):
    app.add_directive("theory", TheoryAdmonition)
    app.add_directive("practice", PracticeAdmonition)
    app.add_directive("example", ExampleAdmonition)
    app.add_directive("key-concept", KeyConceptAdmonition)
    app.add_directive("best-practice", BestPracticeAdmonition)
    app.add_css_file("custom.css")
    app.connect("doctree-resolved", add_target_blank_to_external_links)
    app.connect("source-read", process_substitutions_in_directives)
    app.connect("source-read", retitle_generated_gallery_index)


# ---------------------------------------------------------------------------
# Component base URLs (all external-facing)
# ---------------------------------------------------------------------------
glow_base_url = (
    f"https://{os.getenv('GLOW_DOC_CNAME', 'glow-engine.docs.solutions.ansys.com')}"
)
saf_cli_base_url = (
    f"https://{os.getenv('SAF_CLI_DOC_CNAME', 'saf-cli.docs.solutions.ansys.com')}"
)
bdm_python_api_base_url = "https://bdm-python-api.docs.solutions.ansys.com"
orchestrator_base_url = "https://saf-desktop-orchestrator.docs.solutions.ansys.com"
installer_base_url = "https://saf-desktop-installer.docs.solutions.ansys.com"
testing_base_url = "https://saf-sdk-testing.docs.solutions.ansys.com"
templates_base_url = "https://saf-templates.docs.solutions.ansys.com"
iam_oidc_base_url = "https://ansys-iam-oidc.docs.solutions.ansys.com"
product_config_base_url = "https://saf-product-configuration.docs.solutions.ansys.com"
product_manager_base_url = "https://saf-product-manager.docs.solutions.ansys.com"
translation_base_url = "https://translation-utilities.docs.solutions.ansys.com"
minerva_base_url = "https://ansys-iam-oidc.docs.solutions.ansys.com"  # update when Minerva client publishes docs


SUBSTITUTION_MAPPING = {
    "VERSION": f"v{version}",
    # SAF CLI
    "saf-cli-doc-ref": {"url": saf_cli_base_url, "text": "SAF CLI"},
    "create-solution-ref": {
        "url": f"{saf_cli_base_url}/version/stable/user_guide/creation.html",
        "text": "reference",
    },
    "install-solution-ref": {
        "url": f"{saf_cli_base_url}/version/stable/user_guide/install_solution_environment.html",
        "text": "reference",
    },
    "execute-commands-ref": {
        "url": f"{saf_cli_base_url}/version/stable/user_guide/execute_commands.html",
        "text": "reference",
    },
    "run-solution-ref": {
        "url": f"{saf_cli_base_url}/version/stable/user_guide/run.html",
        "text": "reference",
    },
    "solution-servers-ref": {
        "url": f"{saf_cli_base_url}/version/stable/user_guide/servers.html",
        "text": "reference",
    },
    "configure-additional-services-ref": {
        "url": f"{saf_cli_base_url}/version/stable/user_guide/configure_additional_services.html",
        "text": "reference",
    },
    "cli-cheat-sheet-ref": {
        "url": f"{saf_cli_base_url}/version/stable/cheat_sheet.html",
        "text": "reference",
    },
    "build-distributable-installer-ref": {
        "url": f"{saf_cli_base_url}/version/stable/user_guide/installer.html",
        "text": "reference",
    },
    # GLOW Engine
    "glow-doc-ref": {"url": glow_base_url, "text": "GLOW Engine"},
    "create-solution-definition-ref": {
        "url": f"{glow_base_url}/version/stable/user_guide/solution_definition/solution.html",
        "text": "reference",
    },
    "declare-steps-ref": {
        "url": f"{glow_base_url}/version/stable/user_guide/solution_definition/steps.html",
        "text": "reference",
    },
    "define-transaction-method-ref": {
        "url": f"{glow_base_url}/version/stable/user_guide/solution_definition/transaction_methods/index.html",
        "text": "reference",
    },
    "typing-ref": {
        "url": f"{glow_base_url}/version/stable/user_guide/solution_definition/typing.html",
        "text": "reference",
    },
    "events-ref": {
        "url": f"{glow_base_url}/version/stable/user_guide/solution_definition/events.html",
        "text": "reference",
    },
    "solution-config-ref": {
        "url": f"{glow_base_url}/version/stable/user_guide/solution_definition/solution_configuration.html",
        "text": "reference",
    },
    "using-bdm-ref": {
        "url": f"{glow_base_url}/version/stable/user_guide/working_with_files/using_bdm.html",
        "text": "reference",
    },
    "client-side-interaction-ref": {
        "url": f"{glow_base_url}/version/stable/user_guide/client_side.html",
        "text": "reference",
    },
    "product-instance-management-ref": {
        "url": f"{glow_base_url}/version/stable/user_guide/using_ansys_products/product_instance_management/index.html",
        "text": "reference",
    },
    "job-submission-api-ref": {
        "url": f"{glow_base_url}/version/stable/user_guide/using_ansys_products/job_execution/index.html",
        "text": "reference",
    },
    "minerva-dms-ref": {
        "url": f"{glow_base_url}/version/stable/user_guide/data_management_systems/minerva.html",
        "text": "reference",
    },
    "debugging-ref": {
        "url": f"{glow_base_url}/version/stable/user_guide/debugging/index.html",
        "text": "reference",
    },
    "glow-execution-configuration-ref": {
        "url": f"{glow_base_url}/version/stable/user_guide/glow_execution_configuration/environment_variables.html",
        "text": "reference",
    },
    "glow-api-ref": {
        "url": f"{glow_base_url}/version/stable/api/index.html",
        "text": "GLOW API reference",
    },
    # BDM
    "bdm-python-ref": {"url": bdm_python_api_base_url, "text": "Ansys BDM API"},
    # Orchestrator
    "orchestrator-doc-ref": {
        "url": orchestrator_base_url,
        "text": "SAF Desktop Orchestrator",
    },
    # Installer
    "installer-doc-ref": {"url": installer_base_url, "text": "SAF Desktop Installer"},
    # Testing
    "testing-doc-ref": {"url": testing_base_url, "text": "SAF SDK Testing"},
    # Templates
    "templates-doc-ref": {"url": templates_base_url, "text": "SAF Templates"},
    # Super Components: dash-super-components now lives in the saf metapackage;
    # link to it via the merged api/dash-super-components path instead of a standalone domain.
    # IAM OIDC
    "iam-oidc-doc-ref": {"url": iam_oidc_base_url, "text": "Ansys IAM OIDC"},
    # Product Configuration
    "product-config-doc-ref": {
        "url": product_config_base_url,
        "text": "SAF Product Configuration",
    },
    # Product Manager
    "product-manager-doc-ref": {
        "url": product_manager_base_url,
        "text": "SAF Product Manager",
    },
    # Translation Utilities
    "translation-doc-ref": {
        "url": translation_base_url,
        "text": "SAF Translation Utilities",
    },
    # Minerva
    "minerva-client-doc-ref": {
        "url": minerva_base_url,
        "text": "Minerva Python Client",
    },
    # BDM API (used by migrated glow-engine narrative content)
    "BDM-API": {"url": bdm_python_api_base_url, "text": "BDM Python API"},
    "storage-scope-destroy": {
        "url": f"{bdm_python_api_base_url}/_autosummary/ansys.bdm.api.IStorageScope.destroy.html",
        "text": "storage scope section",
    },
    # Product instance management examples (used by migrated glow-engine narrative content)
    "aedt-example": {
        "url": "https://saf.ansys.com/version/stable/examples/product_instance_managers_examples/saf_ex_aedt_product_instance.html",
        "text": "AEDT solution example",
    },
    "fluent-example": {
        "url": "https://saf.ansys.com/version/stable/examples/product_instance_managers_examples/saf_ex_fluent_product_instance.html",
        "text": "Fluent solution example",
    },
    "geometry-example": {
        "url": "https://saf.ansys.com/version/stable/examples/product_instance_managers_examples/saf_ex_geometry_product_instance.html",
        "text": "Geometry solution example",
    },
    "mapdl-example": {
        "url": "https://saf.ansys.com/version/stable/examples/product_instance_managers_examples/saf_ex_mapdl_product_instance.html",
        "text": "MAPDL solution example",
    },
    "mechanical-example": {
        "url": "https://saf.ansys.com/version/stable/examples/product_instance_managers_examples/saf_ex_mechanical_product_instance.html",
        "text": "Mechanical solution example",
    },
    "optislang-example": {
        "url": "https://saf.ansys.com/version/stable/examples/product_instance_managers_examples/saf_ex_optislang_product_instance.html",
        "text": "optiSLang solution example",
    },
    "configure SSH": {
        "url": "https://docs.github.com/en/authentication/connecting-to-github-with-ssh",
        "text": "Configure SSH with GitHub",
    },
    "git": {
        "url": "https://git-scm.com/",
        "text": "Git",
    },
    "sphinx": {
        "url": "https://www.sphinx-doc.org/en/master/",
        "text": "Sphinx",
    },
    "reStructuredText": {
        "url": "https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html",
        "text": "reStructuredText",
    },
    "saf issues": {
        "url": f"https://{REPOSITORY_URL}/issues",
        "text": "SAF issues",
    },
    "saf discussions": {
        "url": f"https://{REPOSITORY_URL}/discussions",
        "text": "SAF discussions",
    },
    "conventional commits": {
        "url": "https://www.conventionalcommits.org/en/v1.0.0/",
        "text": "Conventional Commits",
    },
    "vale": {
        "url": "https://vale.sh/",
        "text": "Vale",
    },
}

rst_prolog = """
.. include:: /_static/include/roles.rst
"""

rst_epilog = build_rst_epilog()

# Cross-references to labels defined in components not yet migrated to this site
nitpick_ignore = [
    ("ref", "run-solution-index"),
]
