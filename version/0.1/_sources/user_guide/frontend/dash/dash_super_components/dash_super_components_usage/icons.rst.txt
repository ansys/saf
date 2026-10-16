.. _user_guide_frontend_dash_super_components_usage_icons:

Icons
#####

Several components in the Super Components for Dash library support icons to
visually enhance the user interface. For example, ``Authenticator`` allows
adding icons to input fields and buttons using the ``leftSection`` property,
and ``Tree`` supports adding icons to individual tree nodes via the ``icon`` property.

This page describes the available options for specifying icons, along with
their advantages and drawbacks.


Icon options requiring an internet connection
=============================================

When the application is always used in an environment with internet access,
you can use the standard icon approaches available for any Dash application.
The most common option is `DashIconify <https://github.com/snehilvj/dash-iconify>`_,
which renders icons from the `iconify <https://icon-sets.iconify.design/>`_
icon library. It provides a very large selection of icons and requires no icon
file management:

.. code-block:: python

    from dash_iconify import DashIconify

    icon = DashIconify(icon="mdi:user")

These icons are fetched from the iconify CDN at runtime and do not display
when the application is used in an offline environment.


Offline-compatible icon options
===============================

The following options work without an internet connection and are suitable
for applications that may be deployed in restricted environments.


Built-in offline icons from ``svg_icons``
-----------------------------------------

The Super Components for Dash library includes a set of built-in SVG icons
in ``ansys.solutions.dash_super_components.utils.svg_icons``. These icons
can be used through two utility functions, depending on whether you need
an icon string or a rendered HTML element.

**Create a fixed-color base64 icon string with ``create_base64_svg_src()``:**

.. code-block:: python

    from dash_extensions.enrich import html

    from ansys.solutions.dash_super_components.utils.svg_icons import (
        IconNames,
        create_base64_svg_src,
    )

    icon_src = create_base64_svg_src(IconNames.MDI_USER, color="#adb5bd")
    icon = html.Img(src=icon_src)

The ``IconNames`` class lists all available built-in icons. The ``color`` parameter accepts any
CSS color value and defaults to ``"#000"`` (black), allowing you to customize the icon color at
runtime. However, CSS color variables (for example, ``var(--mantine-color-gray-5)``) are not
rendered correctly and thus theme-adaptive colors are not supported.


**Create a theme-adaptive icon element directly with ``create_icon_span()``:**

.. code-block:: python

    from ansys.solutions.dash_super_components.utils.svg_icons import (
        IconNames,
        create_icon_span,
    )

    # Inherits text color from the surrounding component.
    icon = create_icon_span(IconNames.MDI_USER, size_px=16)

    # Or use an explicit color override.
    icon_colored = create_icon_span(
        IconNames.MDI_USER,
        size_px=16,
        color="#adb5bd",
    )

This method creates an ``html.Span`` element that renders the icon as a CSS mask, allowing it to
inherit the surrounding text color by default. You can also specify a custom color via the ``color``
parameter, including CSS color variables (for example, ``var(--mantine-color-gray-5)``) for
theme-adaptive colors.

.. vale Vale.Spelling = NO

For a complete list of available built-in icons, see the
`svg_icons source code <https://github.com/ansys/saf/blob/main/packages/dash-super-components/src/ansys/solutions/dash_super_components/utils/svg_icons.py>`_.
For the full API reference, including the ``IconNames`` enumeration and the
``create_base64_svg_src()``, ``create_icon_span()``, and
``create_image_icon_span()`` functions, see the
`SVG icons API reference <https://super-components-for-dash.docs.solutions.ansys.com/version/stable/api/utilities/svg-icons/index.html>`_.

.. vale Vale.Spelling = YES

**Advantages**:

- Works offline without any internet connection.
- Icon color is customizable at runtime via the ``color`` parameter or by inheriting
  ``currentColor`` from the surrounding component.
- No external dependencies beyond the library itself.

**Drawbacks**:

- Limited to the icons provided in ``IconNames``.


When to use each helper
~~~~~~~~~~~~~~~~~~~~~~~

Use the helper that matches what your target component expects:

- Use ``create_icon_span()`` when the target property accepts
  a Dash HTML element and you want the icon to follow theme text color
  automatically (or use a specific ``color`` override).
- Use ``create_base64_svg_src()`` when the target property expects a string
  value (for example, an image ``src`` field).

In most cases where an HTML element is accepted, prefer
``create_icon_span()`` for built-in icons because it provides
the cleanest API and adaptive color behavior out of the box.


Custom offline icons
--------------------

For icons not available in ``IconNames``, you can provide custom icons using
one of the following approaches.

SVG file in the assets folder
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Place an SVG file in the ``assets/icons/`` folder of your Dash application
and reference it by its relative path. This works for components that accept
a file path as the icon value (for example, the ``icon`` property of
``Tree``).

.. code-block:: python

    icon = "/assets/icons/my_custom_icon.svg"

**Advantages**:

- Works offline.
- No manual encoding required.

**Drawbacks**:

- Requires managing icon files in the ``assets/`` directory.
- Portability: the application must be run in an environment where the icon files are
  present at the expected paths.


Inline base64-encoded SVG
~~~~~~~~~~~~~~~~~~~~~~~~~

You can encode an SVG string directly as a base64 data URI and pass it as
the icon value. This is portable (no external files required) and works
offline. To support runtime color control, parameterize the ``fill`` attribute
of the SVG path, as done in the ``svg_icons`` module:

.. code-block:: python

    import base64

    def create_icon(color: str = "#000000") -> str:
        svg = (
            f"""<svg xmlns="http://www.w3.org/2000/svg" """
            f"""width="24" height="24" viewBox="0 0 24 24">"""
            f"""<path fill="{color}" """
            f"""d="M20 22v-5h-3V7h3V2h2v20zM2 22V2h2v5h3v10H4v5z"/>"""
            f"""</svg>"""
        )
        encoded = base64.b64encode(svg.encode())
        return f"data:image/svg+xml;base64,{encoded.decode()}"

    icon = create_icon(color="#adb5bd")

**Advantages**:

- Works offline.
- Fully portable: no dependency on the file system.

**Drawbacks**:

- SVG strings embedded in code can make the source harder to read.


CSS mask icons for custom offline icons
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For improved color control, you can wrap any local image value (for example, base64 data URI values
or ``/assets/...`` paths) into a theme-adaptive icon span with ``create_image_icon_span()``
(similar to ``create_icon_span()`` for built-in icons).
This allows you to use a local image as a CSS-mask icon that inherits the surrounding text color by
default, or you can specify a custom color:

.. code-block:: python

    from ansys.solutions.dash_super_components.utils.svg_icons import create_image_icon_span

    icon = create_image_icon_span(
        mask_image="/assets/icons/my_custom_icon.svg",
        size_px=16,
        color="#adb5bd",
    )
