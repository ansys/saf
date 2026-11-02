.. _projects_dashboard_migration:

Migrate from SAF Portal Desktop to Projects Dashboard
#####################################################

Projects Dashboard replaces SAF Portal Desktop as the project management page of desktop solutions. Instead of
running in a separate Portal process, it is a Dash component embedded in your Solution UI at the ``/projects`` route.

Complete :ref:`dash_multipage_migration` before you start. The Solution UI must already use multi-page Dash
(``use_pages=True``, ``dash.register_page``, and the ``page.py`` layout from that guide).

The main procedure consists of:

- Make sure ``ansys-saf-projects-dashboard`` is installed in the **solution** virtual environment.
- Register a new page that displays the ``ProjectsDashboard`` component.
- Update the layout and callbacks in ``page.py`` to display pages that don't belong to a project.

Update the dependencies
=======================

.. _projects_dashboard_dependencies:

Projects Dashboard is delivered as the Python package ``ansys-saf-projects-dashboard``. The desktop orchestrator
uses it only when that package is installed in the solution environment where you run ``saf run``.

Replace ``my_solution`` with your registered solution name. ``saf execute`` runs each command in that solution's
virtual environment, not in the SAF CLI environment.

Check whether the package is already there
------------------------------------------

.. _projects_dashboard_check_package:

From your solution project directory:

.. code-block:: console

    saf execute my_solution "python -m pip show ansys-saf-projects-dashboard"

If this prints a version, skip to :ref:`projects_dashboard_register_page`. If it fails, use one of the cases below.

.. important::

   The ``ansys-saf-sdk`` ``all`` extra does **not** install Projects Dashboard. You need the ``desktop`` extra on
   the SDK entry in your ``desktop`` Poetry group, or you must add ``ansys-saf-projects-dashboard`` explicitly.

Case A — Solution uses ``ansys-saf-sdk`` (SAF CLI template layout)
------------------------------------------------------------------

Open ``pyproject.toml``. In ``[tool.poetry.group.desktop.dependencies]``, the SDK line should request the
``desktop`` extra, for example:

.. code-block:: toml

    ansys-saf-sdk = { version = ">=0.4.0,<1.0.0", extras = ["desktop"] }

SDK ``0.4.0`` and later pull in Projects Dashboard through that extra. Use the same SDK version constraint in
every Poetry group that declares ``ansys-saf-sdk``. If a group lists other extras (for example ``core-hps``), keep
those extras on that group's line.

Install or refresh dependencies (adjust the ``--with`` list to match the optional groups your solution uses):

.. code-block:: console

    saf execute my_solution "poetry install --with desktop,ui"

If you still need to raise the SDK constraint, add it in each group that references the SDK, then run
``poetry lock`` and ``poetry install`` again in that environment.

Run the check command again. It must succeed before you change the UI.

Case B — Solution does not use ``ansys-saf-sdk``
------------------------------------------------

Add Projects Dashboard to your ``desktop`` group:

.. code-block:: console

    saf execute my_solution "poetry add ansys-saf-projects-dashboard --group desktop"

Run the check command again.

Register the Projects Dashboard page (``projects_page.py``)
===========================================================

.. _projects_dashboard_register_page:

Add a ``projects_page.py`` module next to ``page.py`` in your UI pages package:

.. code-block:: python

    import os

    import dash
    from ansys_saf_projects_dashboard import ProjectsDashboard

    dash.register_page(
        __name__,
        name="Projects",
        path=os.getenv("SAF_DESKTOP_PROJECTS_DASHBOARD_PATH", "/projects"),
        order=-1,
        # Set to False for every page whose URL doesn't start with /projects/<project_id>, such as this one.
        project_scoped=False,
        projects_dashboard=True,
    )


    def layout(theme: str = "light"):
        """Layout of the projects dashboard page, whose theme follows the color scheme of the app."""
        return ProjectsDashboard(
            id="projects-dashboard",
            apiBaseUrl=os.getenv("GLOW_EXTERNAL_API_URL") or os.getenv("GLOW_API_URL"),
            solutionDescription="View and manage your projects.",
            themeMode=theme,
        )

- ``project_scoped`` tells ``page.py`` whether a page belongs to a project. Keep the default (``True``) for pages
  registered with a ``path_template`` starting with ``/projects/<project_id>``. Set it to ``False`` for any other
  page, such as this dashboard at ``/projects``: such a page uses a fixed ``path``, receives no project, and is not
  shown in the step navigation tree. If you forget it, the page displays a 404 error and appears in the step
  navigation tree.
- Keep your existing project pages unchanged: one landing page at ``/projects/<project_id>`` and step pages at
  ``/projects/<project_id>/<step>``.

Update your main layout and callbacks in ``page.py``
====================================================

Until now, every page of your Solution UI belonged to a project. The Projects Dashboard is the first page that
doesn't. The following steps teach ``page.py`` to tell the two kinds of pages apart. Replace ``MySolution`` with your
solution class.

1. Update the main layout
-------------------------

Add ``id="app-shell"`` to your ``dmc.AppShell`` component, so that the navigation bar can be hidden on the dashboard:

.. code-block:: python

    dmc.AppShell(
        [
            header,
            navbar,
            main_layout,
        ],
        id="app-shell",
        header={"height": 70},
        navbar={
            "width": 300,
            "breakpoint": "sm",
            "collapsed": {"mobile": True},
        },
    ),

If you completed :ref:`dash_multipage_migration`, ``active-page-index`` and ``active-project-id`` are already in
the layout. Add the following three stores next to them. They remember which non-project page is shown and when a
project page must be drawn again:

.. code-block:: python

    dcc.Store(id="active-page-index", data=None),
    dcc.Store(id="active-project-id", data=None),
    dcc.Store(id="active-non-solution-page-index", data=None),
    dcc.Store(id="project-scoped-pathname", data=None),
    dcc.Store(id="project-layout-generation", data=0),

2. Tell project pages from other pages
--------------------------------------

Replace ``get_page_list`` with the following functions. ``_match_solution_page`` finds the project page matching a
URL, ``_match_non_solution_page`` finds pages registered with ``project_scoped=False``, and ``get_page_list`` now
leaves those pages out of the step navigation tree:

.. code-block:: python

    def _is_404_page(page: dict[str, Any]) -> bool:
        return page["module"].split(".")[-1] == "not_found_404"


    def _is_project_scoped(page: dict[str, Any]) -> bool:
        """Pages registered with ``project_scoped=False``, such as the projects dashboard, have no project."""
        return page.get("project_scoped", True)


    def _get_relative_pathname(pathname: str | None) -> str:
        """Return the pathname without the GLOW_UI_PATH_PREFIX part and the surrounding slashes."""
        if not pathname:
            return ""
        return dash.strip_relative_path(pathname) or ""


    def _match_solution_page(pathname: str | None) -> tuple[str, dict[str, Any], str | None] | None:
        """Return the index, the page, and the project ID of the project page matching the pathname."""
        relative_pathname = _get_relative_pathname(pathname)
        path_parts = relative_pathname.split("/") if relative_pathname else []
        for i, page in enumerate(dash.page_registry.values()):
            if _is_404_page(page) or not _is_project_scoped(page) or not page.get("path_template"):
                continue
            template_parts = page["path_template"].strip("/").split("/")
            if len(path_parts) != len(template_parts):
                continue
            project_id = None
            matched = True
            for tp, pp in zip(template_parts, path_parts, strict=True):
                if tp == "<project_id>":
                    project_id = pp
                elif tp != pp:
                    matched = False
                    break
            if matched:
                return str(i), page, project_id
        return None


    def _match_non_solution_page(pathname: str | None) -> str | None:
        """Return the index of the page displayed without a project that matches the pathname."""
        relative_pathname = _get_relative_pathname(pathname)
        for i, page in enumerate(dash.page_registry.values()):
            if _is_404_page(page) or _is_project_scoped(page):
                continue
            if relative_pathname == page["path"].strip("/"):
                return str(i)
        return None


    def get_page_list(theme: str) -> list[dict[str, str | bool]]:
        """Return the steps of the navigation tree, excluding the pages displayed without a project."""
        pages = []
        for i, page in enumerate(dash.page_registry.values()):
            if _is_404_page(page) or not _is_project_scoped(page):
                continue
            icon_name = page.get("icon_asset_name", "carbon--ibm-engineering-workflow-mgmt.svg")
            icon_url = get_asset(icon_name, page.get("icon_asset_path", "icons"), theme)
            pages.append({"id": str(i), "text": page["name"], "icon": icon_url, "expanded": True})
        return pages

3. Resolve the active page from the URL
---------------------------------------

Replace ``resolve_active_page_and_project_information`` with the following callbacks. The first one now relies on
``_match_solution_page``. The second one detects pages without a project. The third one stores the URL of the project
page and increases a counter, which is what triggers drawing the project page in the next step:

.. code-block:: python

    @callback(
        Output("active-page-index", "data"),
        Output("active-project-id", "data"),
        Input("url", "pathname"),
    )
    def resolve_active_page_and_project_information(pathname: str) -> tuple[str | None, str | None]:
        solution_page = _match_solution_page(pathname)
        if solution_page is None:
            return None, None
        index, _, project_id = solution_page
        return index, project_id


    @callback(
        Output("active-non-solution-page-index", "data"),
        Input("url", "pathname"),
    )
    def resolve_active_non_solution_page(pathname: str) -> str | None:
        return _match_non_solution_page(pathname)


    @callback(
        Output("project-scoped-pathname", "data"),
        Output("project-layout-generation", "data"),
        Input("url", "pathname"),
        State("project-scoped-pathname", "data"),
        State("project-layout-generation", "data"),
    )
    def resolve_project_scoped_pathname(pathname: str, current_pathname: str | None, generation: int):
        """Store the pathname of the project page and bump the generation that triggers its rendering."""
        if _match_solution_page(pathname) is None:
            return (None if current_pathname is not None else no_update), no_update
        if pathname == current_pathname:
            return no_update, no_update
        return pathname, generation + 1

4. Display project pages and other pages separately
---------------------------------------------------

.. important::

   **Which pathname a callback that receives a project should use**

   GLOW gives a callback its project by reading the project ID from the URL passed in the input or state that
   matches the ``project: MySolution`` argument. That URL must contain ``/projects/<project_id>``. On ``/projects``
   there is no project ID, so GLOW raises an error before your callback code runs. Checking the URL inside the
   callback is too late.

   - Use ``State("url", "pathname")`` in callbacks that are triggered by components of a step page, such as a
     button in a step. These components only exist on project pages, so the URL always contains a project ID. Your
     existing step callbacks don't need to change.
   - Use ``State("project-scoped-pathname", "data")`` in ``page.py`` callbacks that draw a project page or that use
     ``Input("project-layout-generation", "data")``. This store only holds the URL of a project page, and
     ``project-layout-generation`` only changes on project pages.
   - Never trigger a callback that receives a project with ``Input("url", "pathname")``, and never trigger it with a
     component of the main layout, such as the theme switch or a header button. These callbacks also run on
     ``/projects``.

Remove ``display_project_name`` and ``display_page``. Both receive a project from the URL, so they fail on
``/projects``, which has no project ID. Replace ``display_404_page`` too. Add the following callbacks:

- ``display_solution_page`` draws project pages and shows the project name. It receives a project from GLOW and runs
  only on project pages.
- ``display_non_solution_page`` draws pages without a project, such as the dashboard.
- ``display_404_page`` now shows the 404 page only when the URL matches neither kind of page.

.. code-block:: python

    @callback(
        Output("page-content", "children"),
        Output("project-name", "children"),
        Input("project-layout-generation", "data"),
        State("project-scoped-pathname", "data"),
        State("project-scoped-pathname", "data"),
        prevent_initial_call=True,
    )
    def display_solution_page(_generation: int, project: MySolution, project_scoped_pathname: str | None):
        """Return the layout of the project page, passing the project instance.

        ``project-scoped-pathname`` is passed twice: GLOW injects the project from the first one, and the second one
        gives the raw pathname that selects the page.
        """
        solution_page = _match_solution_page(project_scoped_pathname)
        if solution_page is None:
            return no_update, no_update
        try:
            project_display_name = project.project_display_name
        except NotFoundException:
            return _display_404_page(), ""
        _, page, _ = solution_page
        layout_func = page["layout"]
        if callable(layout_func):
            params = inspect.signature(layout_func).parameters
            page_layout = layout_func(project=project) if "project" in params else layout_func()
        else:
            page_layout = layout_func
        return page_layout, f"Project Name: {project_display_name}"


    @callback(
        Output("page-content", "children"),
        Output("project-name", "children"),
        Input("active-non-solution-page-index", "data"),
        State("color-scheme-switch", "checked"),
        prevent_initial_call=True,
    )
    def display_non_solution_page(active_non_solution_page_index: str | None, switch_on: bool):
        """Return the layout of a page displayed without a project, such as the projects dashboard."""
        if active_non_solution_page_index is None:
            return no_update, no_update
        page = list(dash.page_registry.values())[int(active_non_solution_page_index)]
        layout_func = page["layout"]
        if not callable(layout_func):
            return layout_func, ""
        theme = "dark" if switch_on else "light"
        kwargs = {"theme": theme} if "theme" in inspect.signature(layout_func).parameters else {}
        return layout_func(**kwargs), ""


    @callback(
        Output("page-content", "children"),
        Output("project-name", "children"),
        Input("active-page-index", "data"),
        Input("active-non-solution-page-index", "data"),
        prevent_initial_call=True,
    )
    def display_404_page(active_page_index: str | None, active_non_solution_page_index: str | None):
        if active_page_index is None and active_non_solution_page_index is None:
            return _display_404_page(), ""
        return no_update, no_update

5. Hide the step navigation on the dashboard
--------------------------------------------

Replace ``render_nav_tree``. It now hides the navigation bar on pages without a project:

.. code-block:: python

    @callback(
        Output("navbar-content", "children"),
        Output("app-shell", "navbar"),
        Input("active-page-index", "data"),
        Input("active-non-solution-page-index", "data"),
        Input("color-scheme-switch", "checked"),
        State("app-shell", "navbar"),
        prevent_initial_call=True,
    )
    def render_nav_tree(active_index, active_non_solution_page_index, switch_on, navbar):
        """Display the steps on project pages and collapse the navbar on the other pages."""
        show_navbar = active_index is not None and active_non_solution_page_index is None
        navbar = {**navbar, "collapsed": {"mobile": True, "desktop": not show_navbar}}
        if not show_navbar:
            return html.Div(), navbar
        theme = "dark" if switch_on else "light"
        return Tree(aio_id="navigation_tree", items=get_page_list(theme), selected_item=active_index), navbar

In ``open_new_page``, skip pages without a ``path_template``, right after reading the selected page:

.. code-block:: python

    page = pages[item_index]
    if not page.get("path_template"):
        return no_update

6. Update the dashboard theme without reloading it
--------------------------------------------------

Add the following callback at the end of ``page.py``. When the user switches between light and dark mode, it updates
the dashboard in place. Drawing the dashboard again would reload its list of projects:

.. code-block:: python

    clientside_callback(
        """
        (switchOn) => {
            if (!document.getElementById('projects-dashboard')) {
                return window.dash_clientside.no_update;
            }
            return switchOn ? 'dark' : 'light';
        }
        """,
        Output("projects-dashboard", "themeMode"),
        Input("color-scheme-switch", "checked"),
        prevent_initial_call=True,
    )

Keep your ``return_to_portal`` callback as is. In portal mode, the desktop orchestrator points its **Back to
Projects** button to the Projects Dashboard.

Run the solution
================

Run the solution in portal mode:

.. code-block:: console

    saf run my_solution --portal

When ``ansys-saf-projects-dashboard`` is installed in the solution environment, the log should point to the
Projects Dashboard URL on your Solution UI (the ``/projects`` route), not a separate SAF Portal Desktop window.
The **Back to Projects** control in the header should return to that same page.

Open the URL from the log and confirm that ``/projects`` loads the dashboard. Open a project and confirm that the
UI navigates to ``/projects/<project_id>``, your project landing page.

If the log still mentions SAF Portal Desktop, or ``/projects`` does not load, run the ``pip show`` check in
:ref:`projects_dashboard_check_package` again and fix the dependency case that matches your ``pyproject.toml``.

(Optional) Remove the SAF Portal Desktop dependency
===================================================

If your solution declares ``ansys-saf-desktop-portal`` as a dependency, remove it:

.. code-block:: console

    saf execute my_solution "poetry remove ansys-saf-desktop-portal --group desktop"
