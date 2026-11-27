.. _saf-ex-bdm:

BDM
###

.. topic:: Objective

  Manage the files and directories a solution produces or consumes with the blob data management (BDM) feature: store them from the
  backend, reference them through typed step fields, and read, modify, or upload them from
  the frontend.

  Source code for this example is in the `example solution <https://github.com/ansys/saf/tree/main/examples>`_.


.. _saf-ex-bdm-feature-highlight:

:material-outlined:`emoji_objects;1.25em;sd-text-primary` Feature highlight
============================================================================

Blob management is an essential part of any solution app. A blob is never handled through its path:
it is referenced by an ``EntityHandle``, an immutable value that is persisted in a step field and
shared between the backend and the frontend.

In this example, you learn how to:

- :material-outlined:`data_object;1.25em;saf-objective-icon` Declare **entity handle fields** that
  reference a file or a directory.
- :material-outlined:`save;1.25em;saf-objective-icon` **Store** a file in the storage scope from a
  **transaction method** and read it back from the frontend.
- :material-outlined:`edit;1.25em;saf-objective-icon` **Copy and modify** an existing blob,
  then store the new version.
- :material-outlined:`folder;1.25em;saf-objective-icon` Store a whole **directory** and access its
  content.
- :material-outlined:`cloud_upload;1.25em;saf-objective-icon` Store a file **uploaded from the UI**
  and display it back.
- :material-outlined:`attachment;1.25em;saf-objective-icon` Read a **method asset** shipped with a
  transaction method.

When you complete this example, you can expect the following output in the solution UI:

.. _saf-ex-bdm-output-1:

.. image:: /_static/images/use_case_1_frontend.png
  :width: 50%


.. _saf-ex-bdm-prerequisites:

:material-outlined:`task;1.25em;sd-text-primary` Prerequisites
=========================================================================

The ``BDM`` feature is provided in the |glow-doc-ref|_ package, which is available by default in any SAF-based solution.


.. _saf-ex-bdm-solution:

:octicon:`code-square;1em;sd-text-primary` Coding
======================================================

To manage blobs in a solution, work through the following sequence of sections.


.. _saf-ex-bdm-backend:

:material-outlined:`dns;1.25em;sd-text-primary` Backend
---------------------------------------------------------

Create the solution definition.

.. key-concept:: Entity handle

    An ``EntityHandle`` is a reference to a blob managed by BDM. It is an **immutable value**:
    the blob it points to is never modified in place. To change the content, copy the blob, edit
    the copy, and store it to obtain a new handle.

.. dropdown:: Declare the blob fields
  :open:

  Declare one ``EntityHandle`` field per blob the step has to reference. The ``NO_ENTITY``
  default value means that the field does not reference any blob yet.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/file_handling_step.py
    :language: python
    :caption: solution/file_handling_step.py
    :lines: 29-34
    :emphasize-lines: 4-6

.. key-concept:: Storage scope

    The **storage scope** is the working area of BDM. ``get_storage_root()`` returns the directory
    where blobs are staged, and ``store()`` turns a staged file or directory into an
    ``EntityHandle``. The backend reaches it through ``self.storage_scope`` and the frontend
    through ``project.storage_scope``.

.. dropdown:: Store a file
  :open:

  The ``store_my_file_handle`` transaction method writes a text file in the storage root, stores it,
  and assigns the resulting handle to the ``my_file_handle`` field. The content of the file is passed
  from the frontend as a method argument.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/file_handling_step.py
    :language: python
    :caption: solution/file_handling_step.py
    :pyobject: FileHandlingStep.store_my_file_handle
    :dedent:

.. dropdown:: Store a directory
  :open:

  The ``store_my_directory_handle`` transaction method creates a nested directory structure under
  the storage root, writes a file in it, and stores the **whole directory** as a single handle.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/file_handling_step.py
    :language: python
    :caption: solution/file_handling_step.py
    :pyobject: FileHandlingStep.store_my_directory_handle
    :dedent:

.. key-concept:: Method asset

    A **method asset** is a file shipped with a transaction method. It is resolved at run time with
    ``self.transaction.get_asset_entity_handle()``, which returns an ``EntityHandle`` you read like
    any other blob.

.. dropdown:: Read a method asset
  :open:

  The ``access_and_use_method_asset_file`` transaction method reads the ``my_asset.txt`` asset and
  sends its content to the frontend as an event.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/file_handling_step.py
    :language: python
    :caption: solution/file_handling_step.py
    :pyobject: FileHandlingStep.access_and_use_method_asset_file
    :dedent:


.. _saf-ex-bdm-frontend:

:material-outlined:`web;1.25em;sd-text-primary` Frontend
----------------------------------------------------------

Expose the solution definition in the UI. Each use case described in the following sections is one
card of the file handling page.

.. key-concept:: Callback

    A **callback** is a Dash-decorated function that fires in response to a UI event. In a
    SAF solution, callbacks reach the backend through ``project.steps.<step_name>``, read or
    write fields, and invoke transaction methods. No manual HTTP calls are needed.


Use case 1: Store and access a file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Let the user type the content of a text file, create the file in the backend, and read it back.

.. _saf-ex-bdm-use-case-1-frontend:

.. figure:: /_static/images/use_case_1_frontend.png
  :width: 50%

.. dropdown:: Build the card
  :open:

  The card holds a text area for the content of the file and two buttons: one to create the file
  and one to read it back.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/file_handling_page.py
    :language: python
    :caption: ui/pages/file_handling_page.py
    :start-at: store_and_access_a_file_card = dmc.Card(
    :end-before: modifiy_file_card = dmc.Card(
    :dedent:

.. dropdown:: Create the file
  :open:

  The callback of the **Create file** button invokes the ``store_my_file_handle`` transaction method
  with the text entered by the user and reports the outcome through a notification.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/file_handling_page.py
    :language: python
    :caption: ui/pages/file_handling_page.py
    :pyobject: create_file

.. dropdown:: Read the file
  :open:

  The callback of the **Read file** button resolves the ``my_file_handle`` field with
  ``storage_scope.get_text()`` and displays the content of the blob.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/file_handling_page.py
    :language: python
    :caption: ui/pages/file_handling_page.py
    :pyobject: read_file

Use case 2: Access and modify a file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Extend the previous use case so the user can append text to the file that is already stored. The
edit takes place entirely in the frontend, so no backend code is needed.

.. _saf-ex-bdm-use-case-2-frontend:

.. figure:: /_static/images/use_case_2_frontend.png
  :width: 50%

.. dropdown:: Build the card
  :open:

  The card holds a text area for the text to append and a button that triggers the modification.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/file_handling_page.py
    :language: python
    :caption: ui/pages/file_handling_page.py
    :start-at: modifiy_file_card = dmc.Card(
    :end-before: access_method_assets_card = dmc.Card(
    :dedent:

.. dropdown:: Modify the file
  :open:

  Because an ``EntityHandle`` is immutable, the callback copies the blob with
  ``storage_scope.get_copy()``, edits the copy, and stores it again. The ``my_file_handle`` field is
  then updated with the **new** handle.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/file_handling_page.py
    :language: python
    :caption: ui/pages/file_handling_page.py
    :pyobject: modify_file

Use case 3: Store and access directory content
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Let the user define a relative file path and its content, then store the whole directory structure
in the storage scope.

.. _saf-ex-bdm-use-case-3-frontend:

.. figure:: /_static/images/use_case_3_frontend.png
  :width: 50%


.. dropdown:: Build the card
  :open:

  The card holds a text input for the relative path of the file, a text area for its content, and a
  button that triggers the creation of the directory structure.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/file_handling_page.py
    :language: python
    :caption: ui/pages/file_handling_page.py
    :start-at: store_and_access_a_directory_card = dmc.Card(
    :end-before: return html.Div(
    :dedent:

.. dropdown:: Create the directory
  :open:

  The callback of the **Create file** button invokes the ``store_my_directory_handle`` transaction
  method with the relative path and the content entered by the user.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/file_handling_page.py
    :language: python
    :caption: ui/pages/file_handling_page.py
    :pyobject: create_directory

Use case 4: Store a file uploaded from the frontend
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Let the user upload a file from the UI and store it in the storage scope. As in use case 2, the
whole workflow runs in the frontend, so no backend code is needed.

.. _saf-ex-bdm-use-case-4-frontend:

.. figure:: /_static/images/use_case_4_frontend.png
  :width: 50%

.. dropdown:: Build the card
  :open:

  The card holds a ``dcc.Upload`` component that accepts a PNG file and a ``dmc.Image`` component
  that displays the stored image.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/file_handling_page.py
    :language: python
    :caption: ui/pages/file_handling_page.py
    :start-at: store_uploaded_file_from_ui = dmc.Card(
    :end-before: store_and_access_a_directory_card = dmc.Card(
    :dedent:

.. dropdown:: Store the uploaded file
  :open:

  The callback decodes the uploaded content, writes it in the storage root, and stores it. The URL
  returned by ``get_entity_url()`` is the source of the image component, so the stored blob is
  served directly to the browser.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/file_handling_page.py
    :language: python
    :caption: ui/pages/file_handling_page.py
    :pyobject: upload_file

Use case 5: Read a method asset
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Read a file shipped with a transaction method and push its content to the UI through an event.

.. dropdown:: Build the card
  :open:

  The card holds a button that starts the transaction and a container that displays the content of
  the asset.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/file_handling_page.py
    :language: python
    :caption: ui/pages/file_handling_page.py
    :start-at: access_method_assets_card = dmc.Card(
    :end-before: store_uploaded_file_from_ui = dmc.Card(
    :dedent:

.. dropdown:: Start the transaction
  :open:

  The callback of the **Read method asset file** button invokes the
  ``access_and_use_method_asset_file`` transaction method.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/file_handling_page.py
    :language: python
    :caption: ui/pages/file_handling_page.py
    :pyobject: trigger_transaction_with_method_assets

.. dropdown:: Display the content of the asset
  :open:

  The transaction raises an event instead of writing a field. A second callback listens to the event
  listener registered in the layout and renders the message it carries.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/file_handling_page.py
    :language: python
    :caption: ui/pages/file_handling_page.py
    :pyobject: display_method_asset_content

  Now that your implementation is complete, continue to the :ref:`saf-ex-bdm-testing` section.


.. _saf-ex-bdm-testing:

:octicon:`verified;1em;sd-text-primary`  Testing
==================================================

Finally, test your implementation to confirm it works as expected.

Run the solution and compare your results with the results shown in the
:ref:`Feature highlight <saf-ex-bdm-feature-highlight>` section.
