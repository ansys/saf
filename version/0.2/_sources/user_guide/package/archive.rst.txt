.. _user_guide_archive_a_solution:

Archive a solution
##################

A solution archive is a single file that contains all of the source code for a solution. It is created in the ``.saf`` format and can be used to share a solution or back up its source code.

You can create a solution archive with the ``saf archive`` command in either SAF CLI or Solutions Manager.

.. tab-set::

  .. tab-item:: SAF CLI

    Use SAF CLI to create a solution archive with default values:

    .. tab-set::

      .. tab-item:: Syntax

        .. code-block:: bash

          saf archive <solution_name>

      .. tab-item:: Example

        .. code-block:: bash

          saf archive minimal-solution

  .. tab-item:: Solutions Manager

    Create a solution archive with Solutions Manager:

    #. Open the solution's root directory in Visual Studio Code.

    #. In the Activity Bar, click the **Solutions Manager** icon.

    #. In the **Solutions Manager** panel, expand the **Archive Solution** view:


       .. image:: /_static/images/solutions_manager_archive_view.png
        :alt: Solutions Manager Archive Solution view
        :width: 45%

    #. Fill out the following values:

       a. The **Solution** field is populated with the name of the open solution. Optionally, you can select a different solution to archive.

          To change your selection, select an available solution from the list or browse to a different solution folder. Values in the related fields update automatically.

       b. Select the output directory for the archive.

          By default, the output directory is the current working directory. Browse to a different folder or enter the path manually.

          .. important::

             If you leave the default output directory unchanged, Solutions Manager displays a warning. We recommend changing the path. Saving the archive in the solution's root folder can cause each new archive to include the previous archive file, which can make the solution difficult to extract.

            .. image:: /_static/images/solutions_manager_archive_confirm_path.png
              :alt: Solutions Manager Archive Solution output directory confirmation
              :width: 55%

       c. The **Archive file name** field is populated with the name of the open solution. Optionally, you can enter a different value.

       d. The **Extension** field is populated with the default extension ``.saf``. Optionally, you can enter a different value.

    #. Generate the archive file.

       Click the :guilabel:`Archive solution` button. Alternatively, you can copy the command under **Archive solution command** and run it in the terminal.

       A confirmation message appears when the archive is created successfully.

.. admonition:: Result

  When the solution archive file is created:

  * The archive is named with the solution name and placed in the specified output directory.
  * If an archive with the same name exists on the path, it is overwritten.
  * The archive includes all the solution code but does not include existing projects.

.. note::
  Archiving a solution does not remove it from the solutions registry and does not delete any files. To completely delete a solution, you must manually remove the files from your file system.

.. seealso::
  For information on how to run an archived solution, see :ref:`user_guide_run_archived_solution`.


SAF archive command options
============================

The ``saf archive`` command has several options. To see them all, run the following command:

.. code-block:: text

    saf archive --help

The following ``saf archive`` options are available:

.. list-table::
   :header-rows: 1
   :stub-columns: 1
   :widths: 15 85

   * - Option
     - Description

   * - ``--filename``
     -  Specifies the name of the archive file to create. If not provided, then the solution
        name is used.

   * - ``--extension``
     - Specifies the extension (with the period) of the archive file to create. If not provided, then ``.saf``
       is used.

   * - ``--path``
     -  Specifies the path to save the solution. If not provided, the current working directory
        is used.


SAF archive command example
===========================

This example shows how to use SAF CLI to create a solution archive with specified values.

.. tab-set::

  .. tab-item:: Syntax

    .. code-block:: bash

      saf archive <solution_name_or_path> --path <output_directory> --filename <archive_filename> --extension <archive_extension>

  .. tab-item:: Example

    .. code-block:: text

      saf archive "D:\AnsysDev\Solutions-Manager-Doc-Migration\minimal_solution" --path "d:\AnsysDev\archived_solutions" --filename "archived_minimal_solution" --extension .archive


