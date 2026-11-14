.. _best_practices_dictionary:

Dictionaries
############

A :dfn:`dictionary` is a data type in the solution steps that stores key-value pairs. Each key is unique and is used to access its corresponding value. Dictionaries are mutable, meaning their contents can be modified after creation.

This section covers the following topics related to working with dictionaries:

* Define a dictionary step field
* Access the step field in the frontend
* Modify the step field in a frontend callback
* Access and modify the step field in a transaction method


Define a dictionary step field
===================================

Use the ``dict`` datatype to create a dictionary in the step file. The dictionary can contain multiple data types, including lists, strings, and booleans. You can define the dictionary in the step file using the following code:

.. vale off

.. code-block:: python
    :caption: src/ansys/solutions/demo_solution/solution/**first_step.py**

    data_form: dict = {
        "number_input": 1,
        "Multiple_Number_Input": [0, 10, 20],
        "Text_Input": "Demo",
        "Checkbox": True,
    }

.. vale on

Access the step field in the frontend
=========================================

Use the ``AwcInputForm`` Dash super component to create the solution app's UI. You can access the dictionary step field in the frontend using the following code:

.. vale off

.. code-block:: python
    :caption: src/ansys/solutions/demo_solution/ui/pages/**first_page.py**

    def labels_field_help(step):
        data = AwcInputForm(
            [
                {
                    "label": "Number Input",
                    "fields": [
                        {
                            "type": "NumberInput",
                            "value": step.data_form["number_input"],
                            "id": "number-input-9",
                            "required": True,
                        }
                    ],
                },
                {
                    "label": "Multiple Number Input",
                    "fields": [
                        {
                            "type": "NumberInput",
                            "value": step.data_form["Multiple_Number_Input"][0],
                            "id": "number-input-10",
                            "required": True,
                        },
                        {
                            "type": "NumberInput",
                            "value": step.data_form["Multiple_Number_Input"][1],
                            "id": "number-input-11",
                            "required": True,
                        },
                        {
                            "type": "NumberInput",
                            "value": step.data_form["Multiple_Number_Input"][2],
                            "id": "number-input-12",
                            "required": True,
                        },
                    ],
                },
                {
                    "label": "Text Input",
                    "fields": [
                        {
                            "type": "Input",
                            "placeholder": "Enter a value",
                            "id": "text-input-3",
                            "value": step.data_form["Text_Input"],
                            "required": True,
                        }
                    ],
                },
                {
                    "label": "Checkbox",
                    "fields": [
                        {
                            "type": "Checkbox",
                            "id": "checkbox-3",
                            "checked": step.data_form["Checkbox"],
                        }
                    ],
                },
            ],
            id="labels-fields",
            title="Labels, Fields",
            columns=["label", "fields"],
            column_names=["Label", "Fields"],
        )
        return data

.. vale on

Modify the step field in a frontend callback
==================================================

Use the ``@callback`` decorator to create a callback function that updates the dictionary step field. The callback function is triggered when the user clicks a button in the UI. The function retrieves the values from the input fields and updates the dictionary step field with the new values.

.. code-block:: python
    :caption: src/ansys/solutions/demo_solution/ui/pages/**first_page.py**

    @callback(
        Output("view_data", "children"),
        Input("get-number-inputs", "clicked"),
        State({"form_id": "labels-fields", "type": "awc-input-form-numberinput-field", "index": ALL}, "value"),
        State("url", "pathname"),
    )
    def button_event(click, values, pathname):
        project = DashClient[My_SolutionSolution].get_project(pathname)
        step = project.steps.second_step
        data = step.data_form

        if "get-number-inputs" in ctx.triggered_id:
            data["number_input"] = values[0]
            data["Multiple_Number_Input"] = values[1:]
            step.data_form = data
            return html.Div("Data updated successfully")
        else:
            raise PreventUpdate



Access and modify the step field in a transaction method
===========================================================

Use the ``@transaction`` decorator to create a transaction method that updates the dictionary step field. The ``@transaction`` decorator specifies the download and upload fields. The method retrieves the values from the input fields and updates the dictionary step field with the new values. The updated dictionary is then used to update the step field in the project using ``upload``.

.. code-block:: python
    :caption: src/ansys/solutions/demo_solution/ui/pages/**first_step.py**

    @transaction(self=StepSpec(upload=["data_form"]))
    def update_val(self) -> None:
        """Compute the sum of two numbers."""
        new_dict = {
            "number_input": 125,
            "Multiple_Number_Input": [1, 2, 3],
            "Text_Input": "Text-updated",
            "Checkbox": False,
        }
        self.data_form = new_dict


.. note::
    * The dictionary key must be unique.
    * The dictionary key must be a string.
    * Copy the entire dictionary step field before modifying the items.
    * Use the copied dictionary to update values.
    * Use the modified dictionary to update the dictionary step field.


