.. _customize_dash_ui:

Customize the solution UI
################################

This section describes how to customize the visual identity of your solution's user interface by replacing the default placeholder assets.


Logo
====

The solution template includes a placeholder logo displayed in the top-left corner of the navigation bar.

.. list-table::
   :header-rows: 1

   * - Property
     - Value
   * - Default filename
     - ``placeholder_logo_white.png``
   * - Recommended size
     - 676 × 76 pixels (displayed at 36 pixels height)
   * - Location
     - ``<solution_root>/src/<organization_name>/<solution_module_name>/ui/assets/logos/``

To replace the logo:

1. Prepare a PNG image with a transparent background.
2. Place it in the ``logos/`` directory shown above.
3. If the filename differs from the default, update the reference in ``page.py``:

   .. code-block:: python

      html.Img(src=dash.get_asset_url("logos/placeholder_logo_white.png"), height="36px")

   Replace ``placeholder_logo_white.png`` with the new filename.

.. note::

   The logo is rendered at 36 pixels height regardless of the original image dimensions.


Workflow illustration
=====================

The solution template includes a placeholder workflow image displayed on the About page.

.. list-table::
   :header-rows: 1

   * - Property
     - Value
   * - Default filename
     - ``workflow-placeholder.png``
   * - Recommended size
     - 1280 × 320 pixels
   * - Location
     - ``<solution_root>/src/<organization_name>/<solution_module_name>/ui/assets/images/``

To replace the workflow illustration:

1. Prepare a PNG image.
2. Place it in the ``images/`` directory shown above.
3. If the filename differs from the default, update the reference in ``about_page.py``:

   .. code-block:: python

      dbc.CardImg(src=dash.get_asset_url("images/workflow-placeholder.png"))

   Replace ``workflow-placeholder.png`` with the new filename.
