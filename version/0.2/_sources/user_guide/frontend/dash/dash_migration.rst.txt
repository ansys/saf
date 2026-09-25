.. _dash_multipage_migration:

Migrate the solution UI to a multi-page Dash application
##########################################################

The instructions below assume that your Solution UI follows the structure of the solution template provided by SAF CLI in previous versions.

Nevertheless, the changes are applicable with little modification to any Solution UI using Dash. See `Dash official documentation <https://dash.plotly.com/urls>`_ for more information. The main procedure consists of:

- Enable the multi-page support in your Dash app with ``use_pages=True``.
- Register your pages with ``dash.register_page``.
- Update your callbacks to use the new page registry and URL-based navigation.

Update Dash app initialization in ``app.py``
============================================

Add ``use_pages=True`` to your DashProxy initialization in ``app.py``:

.. code-block:: python

    app = DashProxy(
        __name__,
        suppress_callback_exceptions=True,
        transforms=[TriggerTransform(), MultiplexerTransform()],
        requests_pathname_prefix=f"{os.getenv('GLOW_UI_PATH_PREFIX', '/')}",
        use_pages=True,
    )


Register solution pages (``first_page.py``...)
==============================================

Register your step pages (excluding ``page.py``). Add the following instruction at the top of the file, after the imports:

.. code-block:: python

    dash.register_page(
        __name__,
        name="First Step",
        path_template="/projects/<project_id>/first-step",  # replace first-step with your page name
        icon_asset_name="carbon--ibm-engineering-workflow-mgmt.svg",  # optional, modify as needed for each page
        icon_asset_path="icons",  # optional
    )

- All pages must have a path template that starts with ``/projects/<project_id>/`` followed by a subpath that identifies the step or page, for example, ``/projects/<project_id>/first-step``.
- There should be only **one** page with the path template ``/projects/<project_id>``, without subpath. This will be used as the landing/about/initial page when opening a project.
- You can use the ``order`` parameter in the ``register_page`` function to control the order of the pages in the navigation tree. For example, add ``order=1`` to the first page, ``order=2`` to the second page, and so on.

See `Dash API reference <https://dash.plotly.com/urls#reference-for-dash.register_page>`_ for more details on the parameters of the ``register_page`` function.

Use project in your layout functions instead of step:

.. code-block:: python

    # def layout(step: FirstStep):
    def layout(project: MySolution):
        step = project.steps.first_step

Leave it as ``def layout():`` if it doesn't require step information in the layout.


Update your main callbacks and layout in ``page.py``
====================================================


1. Remove ``get_page_list``, ``display_page`` and ``update_nav_icons`` callbacks. Add the following, replacing ``MySolution`` with your solution class:

    .. code-block:: python

        from typing import Any
        from ansys.saf.glow.client import NotFoundException


        def get_page_list(theme: str) -> list[dict[str, str | bool]]:
            """Return the page list with icons based on the current theme and registered pages."""
            pages = []
            for i, page in enumerate(dash.page_registry.values()):
                if page["module"].split(".")[-1] == "not_found_404":
                    continue
                page_id = str(i)
                page_name = page["name"]
                icon_name = page.get("icon_asset_name", "carbon--ibm-engineering-workflow-mgmt.svg")
                icon_path = page.get("icon_asset_path", "icons")
                icon_url = get_asset(icon_name, icon_path, theme)
                pages.append({"id": page_id, "text": page_name, "icon": icon_url, "expanded": True})
            return pages


        @callback(
            Output("active-page-index", "data"),
            Output("active-project-id", "data"),
            Input("url", "pathname"),
        )
        def resolve_active_page_and_project_information(pathname: str) -> tuple[str | None, str | None]:
            """Resolve the active page index and project ID based on the current URL."""
            # Remove the GLOW_UI_PATH_PREFIX part from pathname
            relative_pathname = dash.strip_relative_path(pathname)
            path_parts = relative_pathname.split("/") if relative_pathname else []
            for i, page in enumerate(dash.page_registry.values()):
                if page["module"].split(".")[-1] == "not_found_404":
                    continue
                template_parts = page["path_template"].strip("/").split("/")
                # look for same parts, excluding <project_id> variable
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
                    return str(i), project_id
            return None, None


        @callback(
            Output("navbar-content", "children"),
            Input("active-page-index", "data"),
            Input("color-scheme-switch", "checked"),
            prevent_initial_call=True,
        )
        def render_nav_tree(active_index: str | None, switch_on: bool):
            """Sync the active tree item based on the active page index."""
            theme = "dark" if switch_on else "light"
            return Tree(aio_id="navigation_tree", items=get_page_list(theme), active_item_id=active_index)


        def _display_404_page() -> Any:
            for module, page in dash.page_registry.items():
                if module.split(".")[-1] == "not_found_404":
                    return page["layout"]
            return html.H1("404 - Page not found")


        @callback(
            Output("page-content", "children"),
            Input("url", "pathname"),
            Input("active-page-index", "data"),
            prevent_initial_call=True,
        )
        def display_page(project: MySolution, active_page_index: str | None):
            """Return the page layout, passing the project instance.

            Using dash.page_container does not allow to inject the project instance as argument to the layout function,
            only supports passing path variables, query parameters or other Inputs/States.
            """
            if active_page_index is None:
                # triggered if pathname with correct project information but incorrect sub-path.
                # anyway, the 404 page will be rendered by another callback
                return no_update
            try:
                # verify that the project information is valid, otherwise return 404.
                # Cannot be done in display_404_page callback because we need that one to succeed if project injection fails.
                _ = project.project_display_name
            except NotFoundException:
                return _display_404_page()
            pages = list(dash.page_registry.values())  # page_registry is an ordered dict
            index = int(active_page_index)
            page = pages[index]
            # support layout module attribute and layout function (with or without project argument)
            layout_func = page["layout"]
            if callable(layout_func):
                params = inspect.signature(layout_func).parameters
                if "project" in params:
                    return layout_func(project=project)
                return layout_func()
            return layout_func


        @callback(
            Output("page-content", "children"),
            Input("active-page-index", "data"),
            prevent_initial_call=True,
        )
        def display_404_page(active_page_index: str | None):
            """Return the 404 page layout when the active page index is None."""
            if active_page_index is None:
                return _display_404_page()
            return no_update


        @callback(
            Output("url", "href"),
            Input(Tree.ids.selected_item("navigation_tree"), "data"),
            State("active-project-id", "data"),
            State("url", "pathname"),
            prevent_initial_call=True,
        )
        def open_new_page(value, project_id: str | None, pathname: str):
            """Navigate to the selected page."""
            if project_id is None or not value:
                return no_update
            item_index = int(Tree.ids.get_index_from_navlink_item_id(value))
            pages = list(dash.page_registry.values())
            if item_index >= len(pages):
                return no_update
            page = pages[item_index]
            # Add GLOW_UI_PATH_PREFIX to the path returned to the browser
            target_path = dash.get_relative_path(
                page["path_template"].replace("<project_id>", project_id)
            )
            if target_path == pathname:
                return no_update
            return target_path


        @callback(
            Output("access-solution-doc", "children"),
            Output("logo-image", "src"),
            Input("color-scheme-switch", "checked"),
        )
        def update_nav_icons(switch_on: bool) -> tuple[html.Img, str]:
            """Update navigation tree icons based on the current theme."""
            theme = "dark" if switch_on else "light"
            return (
                html.Img(src=get_asset("teenyicons--doc-solid.svg", "icons", theme)),
                get_asset("placeholder_logo.png", "logos", theme),
            )


    Note how ``get_page_list`` and ``display_page`` no longer hard code the available pages. Everything is dynamically built and routed using the information of the registered pages. Therefore, future addition or removal of pages will not require any change in these callbacks.

2. In your main layout, change the ``refresh`` attribute of the ``url`` component:

    .. code-block:: python

        # dcc.Location(id="url", refresh=False),
        dcc.Location(id="url", refresh="callback-nav"),


3. In your main layout, remove ``prevent-display`` components and add two new components ``active-page-index`` and ``active-project-id``:

    .. code-block:: python

        html.Div(id="alerts-container", style={"position": "fixed", "top": 90, "right": 10, "width": 350, "zIndex": 1000}),
        # dcc.Store(id="prevent-display", data=None),
        dcc.Store(id="active-page-index", data=None),
        dcc.Store(id="active-project-id", data=None),

4. Replace the content of your navigation tree component (``dmc.AppShellNavbar``) with:

    .. code-block:: python

        navbar = dmc.AppShellNavbar(
            html.Div(),
            id="navbar-content",
            p="md",
        )


(Optional) Add a custom 404 page
================================

You can define a custom 404 page by adding a ``not_found_404.py`` module under your UI pages package:

.. code-block:: python

    import dash
    from dash import html

    dash.register_page(__name__)

    layout = html.H1("This is our custom 404 content")

When this file is present, users will be shown this content if the URL path does not match any of the registered pages.

See `Dash official documentation on default and custom 404 pages <https://dash.plotly.com/urls#default-and-custom-404>`_.
