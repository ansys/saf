.. _saf-ex-file-upload:

File uploads
#############

.. topic:: Objective

    Use a file uploader to add files to the project and display file details in a solution UI.

    Source code for this example is in the `solution-examples <https://github.com/ansys/solution-examples>`_ repository.


.. _saf-ex-file-upload-objective:

:material-outlined:`ads_click;1.25em;sd-text-primary` Objective
==================================================================

A file uploader is a common component in Solutions, as it allows the user to leverage file contents in the workflow. This example demonstrates how to enable end users to upload their own files into a solution. It also shows how to extract details from the project files once they have been uploaded into the solution.

When you complete this example, you can expect the following output in the solution UI:

.. _saf-ex-file-upload-output-1:

.. figure:: /_static/images/usage_file_upload_output_1.png
  :width: 100%

  Uploaded filenames displayed in the solution UI

.. _saf-ex-file-upload-output-2:

.. figure:: /_static/images/usage_file_upload_output_2.png
  :width: 100%

  File details displayed in the solution UI

.. _saf-ex-file-upload-prerequisites:

:material-outlined:`task;1.25em;sd-text-primary` Prerequisites
=========================================================================

.. vale off

To upload files into your solution, you need the ``dcc.Upload`` component from the **Dash Core Components** library. For more information, see the Plotly Dash `dcc.Upload documentation <https://dash.plotly.com/dash-core-components/upload>`_.

.. vale on

.. _saf-ex-file-upload-solution:


:octicon:`code-square;1em;sd-text-primary` Solution
======================================================

To upload files and perform simple file handling tasks, work through the following sequence of tabs.

.. tab-set::

  .. tab-item:: 1️⃣Backend
    :name: saf-ex-file-upload-backend-tab

    Create the solution definition.


    .. dropdown:: Define the step model
      :open:

      Create a ``StepModel`` class named ``FileUploadStep`` with a step field to store all uploaded files to the solution.

      The step field ``project_files`` is a ``FileGroupReference`` that references the group of files in the ``ProjectFiles`` directory. This field is used to reference all of the files that are written to this directory.

      .. code-block:: python
        :caption: solution/file_upload_step.py

        from ansys.saf.glow.solution import FileGroupReference, StepModel


        class FileUploadStep(StepModel):
            """File upload example step model."""

            project_files: FileGroupReference = FileGroupReference("ProjectFiles/*")



  .. tab-item:: 2️⃣Frontend

   Create the page layout with an upload component to allow users to upload files into the solution and add a button to get details on the uploaded files.

   .. dropdown:: Create the page layout with the upload component
    :open:

    To use the ``dcc.Upload`` component:

    #. Import the component from the **Dash Core Components** library and add it to the layout.
    #. Add the following:

       * a ``html.Div`` component to display the list of uploaded files
       * a ``dmc.Button`` to get the file details
       * another ``html.Div`` component to display the file details

    .. code-block:: python
      :caption: ui/pages/file_upload_page

      import base64
      import io
      import logging
      from urllib import parse, request

      from ansys.saf.glow.client import DashClient, callback
      from dash.exceptions import PreventUpdate
      from dash_extensions.enrich import Input, Output, State, dcc, html
      from dash_iconify import DashIconify
      import dash_mantine_components as dmc

      from ansys.solutions.examples.solution.basic.file_upload_step import FileUploadStep
      from ansys.solutions.examples.solution.definition import ExamplesSolution


      def layout(step: FileUploadStep):
          """Layout of the File upload example page."""
          return html.Div(
              [
                  html.Br(),
                  html.H1("File Upload", className="display-3", style={"font-size": "48px", "fontWeight": "bold"}),
                  html.Br(),
                  html.P(
                      "Use a file uploader to add files to the project and display the file size in a solution UI.",
                      className="lead",
                      style={"font-size": "20px"},
                  ),
                  html.Br(),
                  html.Hr(className="my-2"),
                  html.Br(),
                  dcc.Upload(
                      id="dcc-file-upload",
                      children="Drag-and-drop your sample files here",
                      multiple=True,
                      style={
                          "width": "100%",
                          "height": "60px",
                          "borderWidth": "1px",
                          "borderStyle": "dashed",
                          "borderRadius": "5px",
                          "backgroundColor": "#f8f9fa",  # light grey color
                          "textAlign": "center",
                      },
                  ),
                  html.Div(
                      id="upload-output",
                      children="",
                  ),
                  dmc.Button(
                      "Check File Size",
                      id="check-size-button",
                      variant="filled",
                      radius="xl",
                      style={"color": "#FFFFFF", "width": "20%"},
                      leftIcon=DashIconify(icon="fa-solid:info-circle"),
                  ),
                  html.Div(
                      id="file-size",
                      style={
                          "height": "600px",
                          "width": "100%",
                          "overflowY": "scroll",
                          "border": "1px solid #d9d9d9",
                          "borderRadius": "4px",
                          "padding": "8px",
                          "marginTop": "10px",
                      },
                  ),
              ],
          )


   .. dropdown:: Define the interactivity of the page
     :open:

     **Upload files to the project**

     The ``upload_files_to_the_project`` callback function is used to upload the content of the selected files into the project folder anytime the ``contents`` properties for the ``dcc-file-upload`` component changes. If there are any uploaded files, this callback:

     * iterates over each uploaded file,
     * decodes the base64-encoded content,
     * uploads the decoded data to the project using the ``_upload_data_to_project`` function, and
     * adds each filename to the ``uploaded_files`` list that is returned and displayed in the UI.

     .. code-block:: python
       :caption: <ui/pages/file_upload_page>

       @callback(
           Output("upload-output", "children"),
           Input("dcc-file-upload", "contents"),
           State("dcc-file-upload", "filename"),
           State("url", "pathname"),
           prevent_initial_call=True,
       )
       def upload_files_to_the_project(uploaded_file_contents, uploaded_filenames, pathname):
           """Upload files to the project with the Dash Core Components Upload component."""
           if uploaded_filenames:
               project = DashClient[ExamplesSolution].get_project(pathname)
               uploaded_files = []
               if uploaded_file_contents:
                   for filename, content in zip(uploaded_filenames, uploaded_file_contents):
                       data = base64.decodebytes(content.encode("utf8").split(b";base64,")[1])
                       _upload_data_to_project(project, filename, "ProjectFiles", data)
                       uploaded_files.append(filename)
                   return html.P(f"Successfully uploaded files: {', '.join(uploaded_files)}")
           raise PreventUpdate

     **Upload file data to the project**

     The ``_upload_data_to_project`` function uploads the file data to the project. It calls the ``upload_file`` method of the ``project`` object to write the file data to a file named ``filename`` in the ``upload_folder_path``.

     .. code-block:: python
       :caption: ui/pages/file_upload_page

       def _upload_data_to_project(project: FileUploadStep, filename: str, upload_folder_path: str, data):
           """Upload file data to the project."""
           return project.upload_file(f"{upload_folder_path}/{filename}", io.BytesIO(data))

     **Get the file size**

     The ``get_file_size`` callback function gets the file size of the uploaded files anytime the ``n_clicks`` property for the ``check-size-button`` component changes. If there are any uploaded files, this callback:

     * iterates over each uploaded file,
     * gets the file size using the ``_get_file_size`` function, and
     * displays the filename and file size in the UI.

     .. code-block:: python
       :caption: ui/pages/file_upload_page

       @callback(
           Output("file-size", "children"),
           Input("check-size-button", "n_clicks"),
           State("url", "pathname"),
       )
       def get_file_size(n_clicks, pathname):
           """Get the file size of the uploaded files."""
           if n_clicks:
               project = DashClient[ExamplesSolution].get_project(pathname)
               step = project.steps.file_upload_step
               uploaded_files = step.project_files.list_files()
               if uploaded_files:
                   file_sizes = []
                   for file in uploaded_files:
                       file_size = _get_file_size(file.url)
                       filename = _get_file_name(file.url)
                       file_sizes.append((filename, file_size))
                   return [
                       html.P("Project file details:", className="lead", style={"font-size": "20px"}),
                       html.Ul([html.Li(f"{file[0]} (Size: {file[1]} bytes)") for file in file_sizes]),
                   ]
           return []


       def _get_file_name(url: str):
           """Get the file name from the URL."""
           return parse.urlsplit(url).path.split("/")[-1]


       def _get_file_size(url: str):
           """Get the file size from the URL."""
           return len(request.urlopen(url).read())

     Now that your implementation is complete, continue to the :ref:`saf-ex-file-upload-testing`  section.

.. _saf-ex-file-upload-testing:

:octicon:`verified;1em;sd-text-primary`  Testing
==================================================

Finally, test your implementation to confirm it works as expected.

Run the solution and compare your results with the results shown in the :ref:`saf-ex-file-upload-objective` section.
