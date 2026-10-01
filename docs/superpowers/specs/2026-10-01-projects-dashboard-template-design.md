# Projects Dashboard in the minimal solution template — design

- **Issue:** ansys/saf#142 — Include Projects Dashboard in minimal solution template
- **Reference:** ansys/saf-cli#286 (feat: Added projects dashboard to solutions template)
- **Date:** 2026-10-01
- **Status:** Approved approach (A); pending spec review

## Goal

`saf new` (Dash UI) generates a solution that renders `ProjectsDashboard` at `/projects`,
`saf run --portal` opens on that page, and the navbar "Back to projects" button navigates there.

## Constraints

- `ansys-saf-desktop-portal` and `ansys-saf-portal` are **not** replaced. Runtime fallback order is:
  `ansys-saf-projects-dashboard` → `ansys-saf-desktop-portal` → `ansys-saf-portal`.
- Solutions generated before this change (no dashboard dependency) must keep working unchanged.
- A generated solution whose environment lacks the dashboard package must not fail at import time.
- `ansys-saf-projects-dashboard` is not on public PyPI yet (`0.1.dev0`, private Azure feed).

## Existing behavior (no change needed)

`saf-desktop-orchestrator` already implements the runtime chain:

- `Launcher._use_projects_dashboard` is true when `--portal`, a non-Streamlit UI, and
  `importlib.util.find_spec("ansys_saf_projects_dashboard")` all hold (`launcher.py:117`).
- When true: no portal process/port, `GLOW_PORTAL_URL=<ui_url><SAF_DESKTOP_PROJECTS_DASHBOARD_PATH>`
  (default `/projects`), and the UI origin is added to the API's `GLOW_CORS_ORIGINS` (`launcher.py:202-210`).
- When false: `start_portal()` imports `ansys.saf.desktop.portal`, falling back to `ansys.saf.portal`
  (`launcher.py:313-328`).

All of this is covered by existing unit tests in `saf-desktop-orchestrator/tests/unit`.
CORS therefore needs no template change; the template `.env` does **not** get `GLOW_CORS_ORIGINS=["*"]`.

## Changes

### 1. Template dependencies — `packages/saf-cli/.../templates/solution/{{cookiecutter.__solution_name}}/`

- `pyproject.toml`, inside the existing `{% if cookiecutter.__ui_framework == "dash" %}` blocks:
  - Add a supplemental `[[tool.poetry.source]]` `solutions-private-pypi`
    (`https://pkgs.dev.azure.com/ansys-solutions/_packaging/ansys-solutions/pypi/simple/`).
  - Add to `[tool.poetry.group.ui.dependencies]`:
    `ansys-saf-projects-dashboard = { version = ">=0.1.0.dev0,<1.0.0", allow-prereleases = true, source = "solutions-private-pypi" }`.
- Regenerate `lock_files/dash/poetry.lock`. `no_ui` and `streamlit` lock files are untouched.
- While regenerating, check whether the `fastapi` / `opentelemetry-instrumentation-fastapi`
  mismatch noted in #286 (`'_IncludedRouter' object has no attribute 'path'`) reproduces; pin
  `opentelemetry-instrumentation-fastapi>=0.64b0` only if it does.

### 2. Projects page — new `ui/pages/projects_page.py`

- `PROJECTS_DASHBOARD_PATH = os.getenv("SAF_DESKTOP_PROJECTS_DASHBOARD_PATH", "/projects")`.
- `PROJECTS_DASHBOARD_AVAILABLE = importlib.util.find_spec("ansys_saf_projects_dashboard") is not None`.
- Only when available: `dash.register_page(__name__, name="Projects", path=PROJECTS_DASHBOARD_PATH,
  order=-1, project_scoped=False)` and a `layout(theme="light")` that imports the package lazily and
  returns `ProjectsDashboard(id="projects-dashboard", apiBaseUrl=GLOW_EXTERNAL_API_URL or GLOW_API_URL,
  solutionDescription=..., themeMode=theme)`.
- When unavailable the module registers nothing, so `/projects` falls through to the 404 page,
  exactly as today.

### 3. Routing — `ui/app.py`, `ui/pages/page.py`

Port the #286 routing split:

- `app.py` imports `projects_page` (after `DashProxy` init) before `page.layout`.
- Pages carry `project_scoped` (default `True`). Non-project-scoped pages are excluded from the step
  tree and rendered by `display_non_solution_page` without GLOW project injection.
- New stores: `active-non-solution-page-index`, `project-scoped-pathname`, `project-layout-generation`.
  `display_solution_page` is triggered only by `project-layout-generation` so the injected project and
  the rendered page come from the same pathname (avoids the race #286 describes).
- `AppShell` gets `id="app-shell"`; the navbar collapses on non-project-scoped pages.
- `display_404_page` renders 404 only when neither a solution page nor a non-solution page matches.
- Clientside callback syncs `projects-dashboard.themeMode` with the color-scheme switch without
  re-mounting the component (no-op when the dashboard is not in the DOM).

Fixes relative to #286:

- **Back button** (`return_to_portal`): target is `DashClient.get_portal_ui_url()` when set; otherwise
  `PROJECTS_DASHBOARD_PATH` only if `PROJECTS_DASHBOARD_AVAILABLE`; otherwise no button (current
  behavior). Popover text: "Back to Portal" for a non-desktop deployment with a portal URL, else
  "Back to Projects". #286 always fell back to `/projects`, which 404s without the package.
- Document why `display_solution_page` references `State("project-scoped-pathname")` twice (GLOW injects
  `project` from the first; the second yields the raw pathname).
- Do not carry over #286's unrelated changes: saf-cli version bump, beta-release workflow/action.

### 4. Desktop installer — `saf-desktop-installer/_common/utils.py`

`has_portal_dependency` also returns true for `ansys-saf-projects-dashboard` in `poetry.lock`. It drives
whether the installed shortcut launches with `--portal`; without this, a dashboard-only solution would
never open `/projects`. Update the docstring.

## Testing

- **saf-cli unit:** update `tests/unit/mocks/solutions/solution_with_dash_ui` (`app.py`, `pages/page.py`,
  new `pages/projects_page.py`); add `projects_page.py` to the expected files in `tests/outcome_checks.py`.
- **saf-cli e2e (`test_run_solution.py`):** `/projects` renders the dashboard (remove it from the
  404 list, as #286 did); `--portal` opens on `/projects`; the back button href is `/projects`.
- **Fallback coverage:** a test that `projects_page` registers nothing and the back button stays hidden
  when `find_spec` returns `None` and no portal URL is set.
- **saf-desktop-installer unit:** `test_solution_detect_projects_dashboard_dependency` next to the existing
  `test_solution_detect_saf_*_portal_dependency` tests.
- **Orchestrator:** no new tests; existing ones cover detection, URL, and CORS.

## Out of scope / follow-ups

- **saf-sdk extra.** Do not add the dashboard to `ansys-saf-sdk[desktop]`: that extra is shared by
  no-UI and Streamlit solutions and would pull in Dash, and the SDK pins released public-PyPI versions.
  Once the dashboard is published, add a Dash-specific extra (e.g. `ui-dash`) and switch the template's
  `ui` group to it; drop the private-feed source then.
- Streamlit template support.
- PyInstaller exclude list in `solution_package.py` (the dashboard is never in the installer env).
