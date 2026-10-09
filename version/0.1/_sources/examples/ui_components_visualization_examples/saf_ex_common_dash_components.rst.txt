.. _saf-ex-common-dash-components:

Dash components
################

.. topic:: Objective

   Use common Dash components to build page layouts for solution app steps.

   Source code for this example is in the `solution-examples <https://github.com/ansys/solution-examples>`_ repository.


:material-outlined:`ads_click;1.25em;sd-text-primary` Objective
==================================================================

`Dash <https://dash.plotly.com>`_ is a Python framework for building interactive web applications. It is the recommended frontend framework for solution apps for the following reasons:

* Ease of adoption among non-software developers or application engineers
* Strong online community
* Large set of open source component libraries, including:

  * `Dash Core Components <https://dash.plotly.com/dash-core-components>`_
  * `Dash HTML Components <https://dash.plotly.com/dash-html-components>`_
  * `Dash Bootstrap Components <https://dash-bootstrap-components.opensource.faculty.ai/>`_
  * `Community Components Index <https://community.plotly.com/t/community-components-index/60098>`_

This example introduces common Dash UI components that you can start using to build the page layouts for your solution app steps.

:material-outlined:`task;1.25em;sd-text-primary` Prerequisites
=================================================================

To test out the UI components introduced in this example, first generate a solution project and then build the page layout for your solution steps.

.. dropdown:: Generate the solution project
   :open:

   Generate the solution using the ``ansys-templates`` tool, as described in the *Create a Solution* section of the User Guide.

   Then, review the steps in the minimal solution that was generated.

   * In the ``solution`` directory, there are three steps identified as first, second, and third.
   * For each step, there is an associated page module (``<step_name>_page.py``) in the ``ui/pages``
     directory.

   .. code-block:: none
      :emphasize-lines: 13-20

         minimal-solution/
         ├── .github/
         ├── .vscode/
         ├── doc/
         ├── examples/
         ├── src/ansys/solutions/minimal_solution/
         │   │   └──scripts/
         │   ├── solution/
         │   │   ├── definition.py
         │   │   ├── first_step.py
         │   │   ├── second_step.py
         │   │   └── third_step.py
         │   ├── ui/
         │   │   |── assets/
         │   │   |── components/
         │   │   |── pages/
         │   │   │   ├── first_page.py
         │   │   │   |── page.py
         │   │   │   ├── second_page.py
         │   │   │   └── third_page.py
         │   │   └── app.py
         │   └── __init__.py
         ├── tests
         ├── .flake8
         ├── .gitignore
         ├── .pre-commit-config.yaml
         ├── CHANGELOG.md
         ├── CODE_OF_CONDUCT.md
         ├── CONTRIBUTING.md
         ├── LICENSE.rst
         ├── pyproject.toml
         ├── README.rst
         ├── setup_environment.py
         └── tox.ini

.. dropdown:: Build the step page layouts
   :open:


   Build the page layout for each step in the solution.

   The layout of a step is defined in the ``layout`` function of the ``<step_name>_page.py`` module. Build the step layout by adding Dash components to the ``html.Div`` container in this function.


   .. code-block:: python
      :caption: <step_name>_page.py

      from dash_extensions.enrich import dcc, html


      def layout():

          return html.Div(
              [
                  # Add the UI components here
              ]
          )

.. _saf-ex-dash-components-solution:

:octicon:`code-square;1em;sd-text-primary` Components
========================================================

To explore different Dash components, work through the following sequence of tabs.


.. tab-set::

  .. tab-item:: 1️⃣Dash components
   :name: saf-ex-dash-components-tab-1

   Explore the open-source Dash components available in the `Dash Core Components <https://dash.plotly.com/dash-core-components>`_, `Dash HTML Components <https://dash.plotly.com/dash-html-components>`_, and `Dash Bootstrap Components <https://dash-bootstrap-components.opensource.faculty.ai/>`_ libraries.


   .. dropdown:: Getting started
      :open:

      #. The ``dcc`` and ``html`` modules from ``dash_extensions.enrich`` give you access
         to many components, including inputs, checklists, buttons, dropdowns, and more. To use these components, import ``dcc`` and ``html`` with:

         .. code-block:: python

            from dash_extensions.enrich import dcc, html

      #. To access the components from
         `Dash Bootstrap Components <https://dash-bootstrap-components.opensource.faculty.ai/>`_ library, import ``dash_bootstrap_components``:

         .. code-block:: python

            import dash_bootstrap_components as dbc

      Review the component code and output examples that follow.

   .. dropdown:: Input
      :open:

      .. code-block:: python

         dcc.Input(
             id="input-example",
             value="",
             placeholder="Enter a value...",
             type="text",
         )

      .. image:: /_static/images/dash_input.png
         :align: center

   .. dropdown:: Checklist
      :open:

      .. code-block:: python

         dcc.Checklist(
             id="checklist-example",
             options=["Gather data", "Develop model", "Perform analysis"],
             value=["Gather data", "Develop model"],
         )

      .. image:: /_static/images/dash_checklist.png
         :align: center


   .. dropdown:: RadioItems
      :open:

      .. code-block:: python

         dcc.RadioItems(id="radio-items-example", options=["Option 1", "Option 2", "Option 3"], value="Option 2")

      .. image:: /_static/images/dash_radioitems.png
         :align: center


   .. dropdown:: Button
      :open:

      .. code-block:: python

         html.Button(id="button-example", children="Submit")

      .. image:: /_static/images/html_button.png
         :align: center


   .. dropdown:: Dropdown
      :open:

      .. code-block:: python

         dcc.Dropdown(id="dropdown-example", options=["a", "b", "c"], value="a")

      .. image:: /_static/images/dash_dropdown.png
         :align: center


   .. dropdown:: Accordion
      :open:

      .. code-block:: python

         dbc.Accordion(
             [
                 dbc.AccordionItem(
                     [
                         html.P("Accordion content"),  # Add UI components here
                     ],
                     title="Accordion Section",
                     item_id="accordion-example",
                 )
             ]
         )

      .. image:: /_static/images/dash_accordion.png
         :width: 65%

   To continue, click the **2️⃣ Solution components** tab.


  .. tab-item:: 2️⃣Solution components
   :name: saf-ex-dash-components-tab-2

   The **Solutions Dash Library** (``solutions-dash-lib``) is a collection of Ansys-developed reusable components developed to speed up the creation of user interfaces for solution apps.

   The ``InputRow`` and ``OutputRow`` classes are wrappers for several Dash components (such as ``dbc.Row``, ``dbc.Col``, ``dcc.Input``, ``dcc.Dropdown``, and more) to create a row of columns. This example focuses on the input form options.

   .. dropdown:: Getting started
     :open:

     Supported input types:
      * ``label``, ``label_list``
      * ``input``
      * ``number``, ``number_list``
      * ``dropdown``
      * ``checkbox``
      * ``button``
      * ``upload-button``

     Input columns:
      Each supported input type is a row with the following columns:

      * ``Label``
      * ``Input`` (changes for each of the supported types)
      * ``Unit``
      * ``Description``

     .. image:: /_static/images/input_row_all.png
      :width: 85%


     You can access the ``InputRow`` and ``OutputRow`` classes in the ``table`` module of ``ansys.solutions.dash_components.table``.

     For this example, import ``InputRow``:

     .. code-block:: python

       from ansys.solutions.dash_components.table import InputRow

     Review the input type code and output examples that follow.

   .. dropdown:: Label
     :open:

     .. code-block:: python

        InputRow(
            "label",
            row_id="label-id",
            row_label_name="Label",
            row_default_value="Value",
            text_align="left",
        ).get()

     .. image:: /_static/images/input_row_label.png
      :align: center

   .. dropdown:: Label list
     :open:

     .. code-block:: python

      InputRow(
          "label_list",
          row_id="label-list",
          row_label_name="LabelList",
          row_list=["Value", "Unit", "Description"],
          text_align="left",
      ).get()

     .. image:: /_static/images/input_row_label_list.png
      :align: center

   .. dropdown:: Text
     :open:

     .. code-block:: python

      InputRow(
          "input",
          row_id="text-input",
          row_label_name="TextInput",
          row_default_value="a",
          row_description="Enter any string",
          text_align="left",
          disabled=False,
          debounce=True,
      ).get()


     .. image:: /_static/images/input_row_text.png
      :align: center


   .. dropdown:: Number (any)
     :open:

     This input component accepts any number.

     .. code-block:: python

      InputRow(
          "number",
          row_id="number-input",
          row_label_name="NumberInput",
          row_default_value=1.0,
          increment="any",
          row_description="Enter a number",
          text_align="left",
          disabled=False,
          debounce=True,
      ).get()

     .. image:: /_static/images/input_row_number.png
      :align: center


   .. dropdown:: Number (within range)
     :open:

     This input component accepts any number within a specified range.

     .. code-block:: python

      InputRow(
          "number",
          row_id="number-input",
          row_label_name="NumberInput",
          row_default_value=2,
          min_value=0,
          max_value=50,
          increment="any",
          row_description="Enter a number from 0 to 50",
          text_align="left",
          disabled=False,
          debounce=True,
      ).get()


     .. image:: /_static/images/input_row_number_constrained.png
      :align: center

     .. note:: Number validation is included.

      .. image:: /_static/images/input_row_number_constrained2.png
         :align: center



   .. dropdown:: Dropdown
     :open:

     .. code-block:: python

      InputRow(
          "dropdown",
          row_id="dropdown-input",
          row_label_name="DiscreteInput",
          row_list=["a", "b", "c"],
          row_default_value="a",
          row_description="Select a value",
          is_clearable=False,
          disabled=False,
      ).get()


     .. image:: /_static/images/input_row_dropdown.png
      :align: center


   .. dropdown:: Checkbox
     :open:

     .. code-block:: python

      InputRow(
          "checkbox",
          row_id="boolean-input",
          row_label_name="BooleanInput",
          row_default_value=[True],  # [False] or [] for a deselected box. [True] for a checked box
          row_description="Boolean checkbox",
          disabled=False,
      ).get()


     .. image:: /_static/images/input_row_checkbox.png
      :align: center


   .. dropdown:: Button
     :open:

     .. code-block:: python

      InputRow(
          "button",
          row_id="button-id",
          row_label_name="Submit",
          disabled=False,
          text_align="left",
      ).get()


     .. image:: /_static/images/input_row_button.png
      :align: center
      :width: 65%
