.. _saf-ex-bdm:

BDM
###

.. _saf-ex-bdm-summary:

.. topic:: Objective

  Use the ``BDM`` feature to manage files and directories—referred to as BLOBs (Binary Large Objects)—in a solution.

  Source code for this example is in the `solution-examples <https://github.com/ansys/solution-examples>`_ repository.


.. _saf-ex-bdm-objective:

:material-outlined:`ads_click;1.25em;sd-text-primary` Objective
==================================================================

Blob management is an essential part of any solution app. This example shows how to use SAF's ``BDM``
feature to reference and realize blobs in a solution.

.. _saf-ex-bdm-prerequisites:

:material-outlined:`task;1.25em;sd-text-primary` Prerequisites
=========================================================================

The ``BDM`` feature is provided in the |glow-doc-ref|_ package, which is available by default in any SAF-based solution.

.. _saf-ex-bdm-solution:

:octicon:`code-square;1em;sd-text-primary` Solution
======================================================

This section covers a couple of use cases that demonstrate how to use the BDM feature in a solution.

.. tip::

  - Checkout the full backend code of the example in the `solution-examples <https://github.com/ansys/solution-examples/blob/main/src/ansys/solutions/examples/solution/file_handling_step.py>`__.
  - Checkout the full frontend code of the example in the `solution-examples <https://github.com/ansys/solution-examples/blob/main/src/ansys/solutions/examples/ui/pages/file_handling_page.py>`__.


Use case 1: Store and access a file
-----------------------------------

This example shows how to store a file in the storage scope from the solution backend and access it from the solution frontend.

Backend
~~~~~~~

We want to store a text file, named ``my_file.txt``, in the storage scope. The file is generated in a transaction method.
Let's create the corresponding backend code.

.. dropdown:: Backend code

  .. code-block:: python

    from pathlib import Path

    from ansys.saf.glow.solution import NO_ENTITY, EntityHandle, StepModel, StepSpec, transaction


    class FileHandlingStep(StepModel):
        """File handling step model."""

        my_file_handle: EntityHandle = NO_ENTITY

        @transaction(self=StepSpec(upload=["my_file_handle"]))
        def store_my_file_handle(self, text: str) -> None:
            """Store a file in the storage scope."""
            filepath = self.storage_scope.get_storage_root() / "my_file.txt"
            filepath.write_text(text)
            self.my_file_handle = self.storage_scope.store(filepath)

The step model ``FileHandlingStep`` has a field named ``my_file_handle`` of type ``EntityHandle``. This field is used to declare a file handle of the text file.
The default value of this field is ``NO_ENTITY``, which means that the field is not initialized.

The transaction method ``store_my_file_handle`` contains the logic to create a text file named ``my_file.txt`` in the storage scope.
The output field of this method is the file handle, which is stored in the ``my_file_handle`` field. Th transaction takes a string argument ``text``, which is the content
of the file. This text will be defined in the frontend.

Within ``store_my_file_handle``, we are accessing the method storage scope using ``self.storage_scope``. The creation of ``EntityHandle`` from a file happens in two stages.
We first need to place the file within the storage scope directory. To do that we are using ``self.storage_scope.get_storage_root()`` which is returning the directory
that can be used to stage files. Then we are calling ``self.storage_scope.store()`` to create an ``EntityHandle`` from the given file on disk. The created entity handle is
finally assigned to the step field ``self.my_file_handle``.


Frontend
~~~~~~~~

We want to allow the user to define the content of the file and trigger the above transaction to store it in the storage scope.
Let's create a simple card with a text area and two buttons: one to create the file and another to read it.
The user can edit the file content by typing in the text area and clicking the "Create file" button.

.. _saf-ex-bdm-use-case-1-frontend:

.. figure:: /_static/images/use_case_1_frontend.png
  :width: 50%

.. dropdown:: Frontend code: layout

  .. code-block:: python

    import base64

    from ansys.saf.glow.client import DashClient, callback
    from dash_extensions.enrich import Input, Output, State, dcc, html
    from dash_iconify import DashIconify
    import dash_mantine_components as dmc

    from ansys.solutions.examples.solution.definition import ExamplesSolution
    from ansys.solutions.examples.solution.intermediate.file_handling_step import FileHandlingStep


    def layout(step: FileHandlingStep):
        """Layout of the file handling example page."""
        store_and_access_a_file_card = dmc.Card(
            children=[
                dmc.CardSection(
                    dmc.Text("Store and access a file", weight=500),
                    withBorder=True,
                    inheritPadding=True,
                    py="xs",
                ),
                dmc.Space(h=10),
                dmc.Paper(
                    "This example demonstrates how to store a file in the storage scope and access it later. "
                    "Add text to the file via the text area below and click 'Create file'. "
                    "A transaction will be started to create the file and store it in the storage scope. "
                    "You can then read the file by clicking 'Read file'.",
                    shadow="xs",
                ),
                dmc.Space(h=10),
                dmc.Divider(label="Create and store the file"),
                dmc.Textarea(
                    label="Text to add to the file",
                    placeholder="Enter text here...",
                    autosize=True,
                    minRows=2,
                    required=True,
                    id="create-file-text-area-1",
                ),
                dmc.Space(h=10),
                dmc.Button(
                    "Create file",
                    id="create-file-button-1",
                ),
                dmc.Space(h=10),
                dmc.Divider(label="Access the file"),
                dmc.Space(h=10),
                dmc.Button(
                    "Read file",
                    id="read-file-button-1",
                ),
                dmc.Space(h=10),
                html.Div(
                    id="file-content-1",
                    style={"maxHeight": "600px", "width": "100%", "overflowY": "scroll"},
                ),
            ],
            withBorder=True,
            shadow="sm",
            radius="md",
            style={"width": 500},
        )

        return html.Div(
            [
                html.Br(),
                html.H1("File Handling", className="display-3", style={"font-size": "48px", "fontWeight": "bold"}),
                html.P(
                    "Use BDM to manipulate files/folders in the storage scope.",
                    className="lead",
                    style={"font-size": "20px"},
                ),
                html.Hr(className="my-2"),
                html.Br(),
                dmc.Grid(
                    [
                        dmc.Col(
                            [
                                store_and_access_a_file_card,
                            ],
                            span=4,
                        ),
                    ],
                    gutter="xs",
                    grow=True,
                ),
                html.Div(id="notifications-container"),
                DashClient.create_event_listener(step, stream_name="my-stream", id="ws"),
            ]
        )

Let's create one callback to handle the "Create file" button click.

.. dropdown:: Frontend code: callback

  .. code-block:: python

    @callback(
        Output("notifications-container", "children"),
        Input("create-file-button-1", "n_clicks"),
        State("create-file-text-area-1", "value"),
        State("url", "pathname"),
        prevent_initial_call=True,
    )
    def create_file(n_clicks: int, text: str, pathname: str) -> str:
        """Create a file with the given text."""
        project = DashClient[ExamplesSolution].get_project(pathname)
        try:
            project.steps.file_handling_step.store_my_file_handle(text=text)
            title, icon, message = "Success", "ep:success-filled", f"File created successfully."
        except Exception as e:
            title, icon, message = "Error", "material-symbols:error", f"Failed to create file: {str(e)}"

        return dmc.Notification(
            title=title,
            message=message,
            icon=DashIconify(icon=icon),
            action="show",
            id="create-file-notification",
        )

Let's create another callback to handle the "Read file" button click.

.. dropdown:: Frontend code: callback

  .. code-block:: python

    @callback(
        Output("notifications-container", "children"),
        Output("file-content-1", "children"),
        Input("read-file-button-1", "n_clicks"),
        State("url", "pathname"),
        prevent_initial_call=True,
    )
    def read_file(n_clicks: int, pathname: str) -> str:
        """Read the file created in the storage scope."""
        project = DashClient[ExamplesSolution].get_project(pathname)
        try:
            with project.get_storage_scope() as storage_scope:
                content = storage_scope.get_text(project.steps.file_handling_step.my_file_handle)
            title, icon, message = "Success", "ep:success-filled", f"File read successfully."
        except Exception as e:
            title, icon, message = "Error", "material-symbols:error", f"Failed to read file: {str(e)}"

        return (
            dmc.Notification(
                title=title,
                message=message,
                icon=DashIconify(icon=icon),
                action="show",
                id="read-file-notification",
            ),
            html.Div(
                [
                    html.Pre(
                        content,
                        style={"whiteSpace": "pre-wrap", "wordBreak": "break-all", "fontSize": "10px"},
                    )
                ]
            ),
        )

Use case 2: Access and modify a file
------------------------------------

In this use case, we will extend the previous example to allow the user to modify the content of the file and store it back
in the storage scope. The file edit will take place in the frontend side. No backend code changes are needed.

Backend
~~~~~~~

N/A

Frontend
~~~~~~~~

Let's create a simple card with a text area to allow the user to edit the file content and a button to save the changes.

.. _saf-ex-bdm-use-case-2-frontend:

.. figure:: /_static/images/use_case_2_frontend.png
  :width: 50%

.. dropdown:: Frontend code: layout

  .. code-block:: python

    import base64

    from ansys.saf.glow.client import DashClient, callback
    from dash_extensions.enrich import Input, Output, State, dcc, html
    from dash_iconify import DashIconify
    import dash_mantine_components as dmc

    from ansys.solutions.examples.solution.definition import ExamplesSolution
    from ansys.solutions.examples.solution.intermediate.file_handling_step import FileHandlingStep


    def layout(step: FileHandlingStep):
        """Layout of the file handling example page."""

        modifiy_file_card = dmc.Card(
            children=[
                dmc.CardSection(
                    dmc.Text("Access and modify a file", weight=500),
                    withBorder=True,
                    inheritPadding=True,
                    py="xs",
                ),
                dmc.Space(h=10),
                dmc.Paper(
                    "This example demonstrates how to access and modify a file. "
                    "The EntityHandle is intended to represent an immutable value. "
                    "Therefore, you must not modify the file directly. "
                    "Instead, you can create a copy using the get_copy() method, modify it, and then store it. "
                    "Use the text area below to modify the file content. "
                    "Then click 'Modify file' to create a new file with the modified content. ",
                    shadow="xs",
                ),
                dmc.Space(h=10),
                dmc.Divider(label="Access and modify the file"),
                dmc.Textarea(
                    label="Text to add to the existing file",
                    placeholder="Enter text here...",
                    autosize=True,
                    minRows=2,
                    required=True,
                    id="modify-file-text-area-2",
                ),
                dmc.Space(h=10),
                dmc.Button(
                    "Modify file",
                    id="modify-file-button-2",
                ),
                dmc.Space(h=10),
                dmc.Divider(label="Access the file"),
                dmc.Space(h=10),
                html.Div(
                    id="file-content-2",
                    style={"maxHeight": "600px", "width": "100%", "overflowY": "scroll"},
                ),
            ],
            withBorder=True,
            shadow="sm",
            radius="md",
            style={"width": 500},
        )


    return html.Div(
        [
            html.Br(),
            html.H1("File Handling", className="display-3", style={"font-size": "48px", "fontWeight": "bold"}),
            html.P(
                "Use BDM to manipulate files/folders in the storage scope.",
                className="lead",
                style={"font-size": "20px"},
            ),
            html.Hr(className="my-2"),
            html.Br(),
            dmc.Grid(
                [
                    dmc.Col(
                        [
                            modifiy_file_card,
                        ],
                        span=4,
                    ),
                ],
                gutter="xs",
                grow=True,
            ),
            html.Div(id="notifications-container"),
            DashClient.create_event_listener(step, stream_name="my-stream", id="ws"),
        ]
    )

Let's create one callback to handle the "Modify file" button click.

.. dropdown:: Frontend code: callback

  .. code-block:: python

    @callback(
        Output("notifications-container", "children"),
        Output("file-content-2", "children"),
        Input("modify-file-button-2", "n_clicks"),
        State("modify-file-text-area-2", "value"),
        State("url", "pathname"),
        prevent_initial_call=True,
    )
    def modify_file(n_clicks: int, text: str, pathname: str) -> str:
        """Create a file with the given text."""
        project = DashClient[ExamplesSolution].get_project(pathname)
        try:
            with project.get_storage_scope() as storage_scope:
                root = storage_scope.get_storage_root()
                new_file = root / "modified_file.txt"
                storage_scope.get_copy(project.steps.file_handling_step.my_file_handle, new_file)
                content = new_file.read_text()
                content += "\n" + text
                new_file.write_text(content)
                project.steps.file_handling_step.my_file_handle = storage_scope.store(new_file)

            title, icon, message = "Success", "ep:success-filled", f"File modified successfully."
        except Exception as e:
            title, icon, message = "Error", "material-symbols:error", f"Failed to modify file: {str(e)}"

        return (
            dmc.Notification(
                title=title,
                message=message,
                icon=DashIconify(icon=icon),
                action="show",
                id="modify-file-notification",
            ),
            html.Div(
                [
                    html.Pre(
                        content,
                        style={"whiteSpace": "pre-wrap", "wordBreak": "break-all", "fontSize": "10px"},
                    )
                ]
            ),
        )

In this callback, we are accessing the storage scope using ``project.get_storage_scope()``.
We are creating a copy of the file using ``storage_scope.get_copy()``. This is absolutely necessary, because the
``EntityHandle`` is intended to represent an immutable value.

Then we are modifying the content of the file and storing it back in the storage scope using ``storage_scope.store()``.
Finally, we are updating the step field ``my_file_handle`` with the new file handle.

Use case 3: Store and access directory content
----------------------------------------------

In this use case, we will store a directory in the storage scope and access its content from the frontend.

Backend
~~~~~~~

Let's create a transaction method that will create a file within a nested directory structure and store it in the storage scope.

.. dropdown:: Backend code

  .. code-block:: python

    from pathlib import Path

    from ansys.saf.glow.solution import NO_ENTITY, EntityHandle, StepModel, StepSpec, transaction


    class FileHandlingStep(StepModel):
        """File handling step model."""

        my_directory_handle: EntityHandle = NO_ENTITY

        @transaction(self=StepSpec(upload=["my_directory_handle"]))
        def store_my_directory_handle(self, relative_path: str, text: str):
            """Store a directory in the storage scope."""
            relative_path_stripped = str(Path(relative_path).parent).lstrip("\\/")
            dirpath = self.storage_scope.get_storage_root() / relative_path_stripped
            dirpath.mkdir(parents=True, exist_ok=True)
            file_name = Path(relative_path).name
            (dirpath / file_name).write_text(text)
            self.my_directory_handle = self.storage_scope.store(dirpath)

``my_directory_handle`` is a field of type ``EntityHandle`` that will hold the directory handle.
The transaction method ``store_my_directory_handle`` takes two arguments: ``relative_path`` and ``text``.
The ``relative_path`` is the path to the file within the directory structure, and ``text`` is the content of the file.
The method creates a directory structure based on the relative path, writes the file with the given content, and stores
the directory in the storage scope.

Frontend
~~~~~~~~

Let's create a simple card with a text input field to allow the user to define the relative path of the file within the directory
structure, and a text area to allow the user to define the content of the file.

.. _saf-ex-bdm-use-case-3-frontend:

.. figure:: /_static/images/use_case_3_frontend.png
  :width: 50%


.. dropdown:: Frontend code: layout

  .. code-block:: python

    import base64

    from ansys.saf.glow.client import DashClient, callback
    from dash_extensions.enrich import Input, Output, State, dcc, html
    from dash_iconify import DashIconify
    import dash_mantine_components as dmc

    from ansys.solutions.examples.solution.definition import ExamplesSolution
    from ansys.solutions.examples.solution.intermediate.file_handling_step import FileHandlingStep


    def layout(step: FileHandlingStep):
        """Layout of the file handling example page."""

        store_and_access_a_directory_card = dmc.Card(
            children=[
                dmc.CardSection(
                    dmc.Text("Store and access directory content", weight=500),
                    withBorder=True,
                    inheritPadding=True,
                    py="xs",
                ),
                dmc.Paper(
                    "This example demonstrates how to store a directory in the storage scope and access it later. "
                    "Use the relative file path input to generate a file under a directory structure. "
                    "Add text to the file via the text area below and click 'Create file'. "
                    "A transaction will be started to create the file and parent directories and store them in "
                    "the storage scope. You can then read the file by clicking 'Read file'.",
                    shadow="xs",
                ),
                dmc.Space(h=10),
                dmc.Divider(label="Create and store the folder and file"),
                dmc.Space(h=10),
                dmc.TextInput(
                    label="Relative file path",
                    required=True,
                    placeholder="/dir-A/dir-B/file.txt",
                    id="file-path-input",
                ),
                dmc.Space(h=10),
                dmc.Textarea(
                    label="Text to add to the file",
                    placeholder="Enter text here...",
                    autosize=True,
                    minRows=2,
                    required=True,
                    id="create-file-text-area-5",
                ),
                dmc.Space(h=10),
                dmc.Divider(label="Access the file"),
                dmc.Space(h=10),
                dmc.Button(
                    "Create file",
                    id="create-file-button-5",
                ),
            ],
            withBorder=True,
            shadow="sm",
            radius="md",
            style={"width": 500},
        )

        return html.Div(
            [
                html.Br(),
                html.H1("File Handling", className="display-3", style={"font-size": "48px", "fontWeight": "bold"}),
                html.P(
                    "Use BDM to manipulate files/folders in the storage scope.",
                    className="lead",
                    style={"font-size": "20px"},
                ),
                html.Hr(className="my-2"),
                html.Br(),
                dmc.Grid(
                    [
                        dmc.Col(store_and_access_a_directory_card, span=4),
                    ],
                    gutter="xs",
                    grow=True,
                ),
                html.Div(id="notifications-container"),
                DashClient.create_event_listener(step, stream_name="my-stream", id="ws"),
            ]
        )

Let's create one callback to handle the creation of the file and the directory structure.

.. dropdown:: Frontend code: callback

  .. code-block:: python

    @callback(
        Output("notifications-container", "children"),
        Input("create-file-button-5", "n_clicks"),
        State("file-path-input", "value"),
        State("create-file-text-area-5", "value"),
        State("url", "pathname"),
        prevent_initial_call=True,
    )
    def create_directory(n_clicks: int, relative_path: str, text: str, pathname: str) -> str:
        """Create a file with the given text."""
        project = DashClient[ExamplesSolution].get_project(pathname)
        try:
            project.steps.file_handling_step.store_my_directory_handle(relative_path=relative_path, text=text)
            title, icon, message = "Success", "ep:success-filled", f"Directory created successfully."
        except Exception as e:
            title, icon, message = "Error", "material-symbols:error", f"Failed to create directory: {str(e)}"

        return dmc.Notification(
            title=title,
            message=message,
            icon=DashIconify(icon=icon),
            action="show",
            id="trigger-transaction-notification",
        )

Use case 4: Store a file uploaded from the frontend
---------------------------------------------------

A very common use case is to allow the user to upload a file from the frontend and store it in the storage scope.
In this use case, no backend code changes are needed. The file upload and storage will be handled in the frontend.

Backend
~~~~~~~

None

Frontend
~~~~~~~~

Let's create a simple card with a file upload component to allow the user to upload a file and store it in the storage scope.

.. _saf-ex-bdm-use-case-4-frontend:

.. figure:: /_static/images/use_case_4_frontend.png
  :width: 50%

.. dropdown:: Frontend code: layout

  .. code-block:: python

    import base64

    from ansys.saf.glow.client import DashClient, callback
    from dash_extensions.enrich import Input, Output, State, dcc, html
    from dash_iconify import DashIconify
    import dash_mantine_components as dmc

    from ansys.solutions.examples.solution.definition import ExamplesSolution
    from ansys.solutions.examples.solution.intermediate.file_handling_step import FileHandlingStep


    def layout(step: FileHandlingStep):
        """Layout of the file handling example page."""

        store_uploaded_file_from_ui = dmc.Card(
            children=[
                dmc.CardSection(
                    dmc.Text("Store uploaded image", weight=500),
                    withBorder=True,
                    inheritPadding=True,
                    py="xs",
                ),
                dmc.Space(h=10),
                dmc.Paper(
                    "This example shows how to store a file (.png) uploaded from the UI. "
                    "Use the upload component below to select an image file. "
                    "The selected image will be stored in the storage scope and displayed below.",
                    shadow="xs",
                ),
                dmc.Space(h=10),
                dcc.Upload(
                    id="upload-file",
                    multiple=False,
                    accept=".png",
                    children=html.Div(
                        "Drag and drop or click to select an image to upload",
                    ),
                    style={
                        "width": "100%",
                        "height": "60px",
                        "lineHeight": "60px",
                        "borderWidth": "1px",
                        "borderStyle": "dashed",
                        "borderRadius": "5px",
                        "textAlign": "center",
                        "margin": "10px",
                    },
                ),
                dmc.Space(h=10),
                dmc.Image(
                    id="uploaded-image",
                    withPlaceholder=True,
                    placeholder="No image uploaded",
                ),
            ],
            withBorder=True,
            shadow="sm",
            radius="md",
            style={"width": 500},
        )

Let's create one callback to handle the file upload and store it in the storage scope.

.. dropdown:: Frontend code: callback

  .. code-block:: python

    @callback(
        Output("uploaded-image", "src"),
        Input("upload-file", "contents"),
        State("upload-file", "filename"),
        State("url", "pathname"),
        prevent_initial_call=True,
    )
    def upload_file(contents: str, filename: str, pathname: str) -> str:
        """Create a file with the given text."""
        project = DashClient[ExamplesSolution].get_project(pathname)
        content_type, content_string = contents.split(",")
        content = base64.b64decode(content_string)
        with project.get_storage_scope() as storage_scope:
            filepath = storage_scope.get_storage_root() / filename
            filepath.write_bytes(content)
            project.steps.file_handling_step.my_uploaded_file_handle = storage_scope.store(filepath)
        return project.steps.file_handling_step.get_entity_url("my_uploaded_file_handle")

.. _saf-ex-bdm-testing:

:octicon:`verified;1em;sd-text-primary` Testing
==================================================

Finally, test your implementation to confirm it works as expected.

Run the solution and compare your results with the results shown in the :ref:`saf-ex-bdm-objective` section.
