.. _saf-ex-display-images:

File-based images
##################

.. topic:: Objective

  Display images produced by a solution in its UI: generate the image files in the backend,
  store them as blobs, and render them in the frontend from the URLs exposed by their
  entity handles.

  Source code for this example is in the `example solution <https://github.com/ansys/saf/tree/main/examples>`_.


.. _saf-ex-display-images-feature-highlight:

:material-outlined:`emoji_objects;1.25em;sd-text-primary` Feature highlight
============================================================================

The user interface (UI) of a solution app can display both **input data** (such as strings, integers, floats, and files) and **output data** (such as 1D/2D/3D graphics, 3D viewers, and images).

Images are a particular case of output data: they are produced as **files** by the backend, and the
frontend needs a URL rather than a path to render them.

In this example, you learn how to:

- :material-outlined:`image;1.25em;saf-objective-icon` Generate image files in a **transaction
  method** and store them in the storage scope.
- :material-outlined:`data_object;1.25em;saf-objective-icon` Collect the resulting handles in a
  **typed step field** that references a list of blobs.
- :material-outlined:`link;1.25em;saf-objective-icon` Turn those handles into **URLs** that the
  browser can fetch.
- :material-outlined:`bolt;1.25em;saf-objective-icon` Wire a **callback** so a button click
  regenerates the images and refreshes the page.

When you complete this example, you can expect the following output in the solution UI:

.. _saf-ex-display-images-output-1:

.. image:: /_static/images/output_01.png
  :width: 85%


.. _saf-ex-display-images-prerequisites:

:material-outlined:`task;1.25em;sd-text-primary` Prerequisites
=========================================================================

To mimic the creation of files, you need the `pillow <https://pypi.org/project/pillow/>`_ Python imaging library. Install the library using the following command:

.. code-block:: bash

   poetry add pillow



.. _saf-ex-display-images-solution:

:octicon:`code-square;1em;sd-text-primary` Coding
======================================================

To display images from files stored in your solution, work through the following sequence of sections.


.. _saf-ex-display-images-backend:

:material-outlined:`dns;1.25em;sd-text-primary` Backend
---------------------------------------------------------

Create the solution definition.

.. key-concept:: Typed field

    A field is a class attribute with a **type annotation** and a default value. A field
    annotated with ``list[EntityHandle]`` references a list of blobs: the images are not
    stored in the field itself, only the handles that point to them.

.. dropdown:: Define the step field
  :open:

  Declare a ``result_files`` field to hold the handle of each generated image.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/basic_step.py
    :language: python
    :caption: solution/basic_step.py
    :lines: 73
    :dedent:

.. key-concept:: Transaction method

    A **transaction method** is the only place where step fields are read and written. Any
    method that touches a field must be decorated with ``@transaction``, which declares the
    fields it downloads (reads) and uploads (writes) through its ``StepSpec``.

.. dropdown:: Add a transaction method to create the images
  :open:

  The ``create_images`` transaction method mimics an automated workflow: it generates three
  PNG files with the ``pillow`` library in the storage root of the step, stores each of them
  through ``self.storage_scope.store()``, and collects the returned handles in the
  ``result_files`` field.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/basic_step.py
    :language: python
    :caption: solution/basic_step.py
    :pyobject: BasicStep.create_images
    :dedent:


.. _saf-ex-display-images-frontend:

:material-outlined:`web;1.25em;sd-text-primary` Frontend
----------------------------------------------------------

Expose the solution definition in the UI.

.. dropdown:: Define the page layout
  :open:

  In the ``ui/pages`` folder, the ``layout`` function of the page creates the
  :guilabel:`Create and display images` button and a ``div`` named ``result-images`` that holds
  the images to display. Its children are built by the ``create_image_div`` function.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/basic/display_images_page.py
    :language: python
    :caption: ui/pages/basic/display_images_page.py
    :pyobject: layout

.. key-concept:: Callback

    A **callback** is a Dash-decorated function that fires in response to a UI event. In a
    SAF solution, callbacks reach the backend through ``project.steps.<step_name>``, read or
    write fields, and invoke transaction methods — no manual HTTP calls needed.

.. dropdown:: Trigger the image creation from the frontend
  :open:

  Write a callback that invokes the ``create_images`` transaction method when the button is
  clicked, then rebuilds the content of the ``result-images`` div with the newly created images.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/basic/display_images_page.py
    :language: python
    :caption: ui/pages/basic/display_images_page.py
    :pyobject: create_images

.. key-concept:: File URL

    The browser cannot read a blob from its path. Call ``get_data`` with
    ``substitute_file_handles_with_urls=True`` to retrieve a field whose entity handles are
    replaced by URLs that the browser can fetch.

.. dropdown:: Render the images
  :open:

  The ``create_image_div`` function reads the ``result_files`` field as a list of URLs and wraps
  each of them in an ``html.Img`` component. A timestamp is appended to every URL so that the
  browser does not serve a cached version of a previously generated image.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/basic/display_images_page.py
    :language: python
    :caption: ui/pages/basic/display_images_page.py
    :pyobject: create_image_div

  Now that your implementation is complete, continue to the :ref:`saf-ex-display-images-testing` section.


.. _saf-ex-display-images-testing:

:octicon:`verified;1em;sd-text-primary`  Testing
==================================================

Finally, test your implementation to confirm it works as expected.

Run the solution and compare your results with the results shown in the
:ref:`Feature highlight <saf-ex-display-images-feature-highlight>` section.
