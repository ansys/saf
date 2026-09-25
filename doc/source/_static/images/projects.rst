.. _manage_projects:

Manage projects
################

SAF supports and provides persistence for an arbitrary set of solution instances called :dfn:`projects`. A solution project consists of the project data and project files.

The contents of the project data are determined by the data schema in the solution definition. Once you've created a project, you can use GLOW's Client API and REST API to manipulate its contents.

.. important::
    Do not modify or delete projects manually by directly editing or removing the project data or files, as this may invalidate the state of the project or its contents. Make sure that you perform all project operations either from the Portal or Solution UI (where applicable) or by using the development tools provided by SAF.


Create a project
================

You can create a project either from SAF Portal or via SAF CLI.

.. tab-set::

  .. tab-item:: SAF Portal

    #. Run the solution with the ``--portal`` option.
    #. Click :guilabel:`New project`.
    #. Enter a display name for the project.
    #. Fill the description for the project. (optional)
    #. Click :guilabel:`Create`.

    SAF Portal automatically launches the Solution UI for the new project.

    .. image:: /_static/images/projects_create_project.png
      :alt: Create project in SAF Portal

  .. tab-item:: SAF CLI

    Run the solution with the ``--project <project-name>`` option.

    .. warning::

      Options ``--portal`` and ``--project <project-name>`` cannot be used together.


Export/share a project
=======================

You can collaborate with others by packaging and sharing projects. A project package (``.safx`` file) allows you to share a complete project.

To create a ``.safx`` project package, you need to export your project using SAF Portal:

#. Run the solution with the ``--portal`` option.
#. Find the project to export, click the button for more options and click :guilabel:`Export`.

The file is downloaded to the **Downloads** directory of the browser. You can share the ``.safx`` file so it can be imported by other users using SAF Portal.

.. image:: /_static/images/projects_export_project.png
   :alt: Export project in SAF Portal

Import a project package
========================

You can import a project package (``.safx`` file) into SAF using SAF Portal.

.. note::
  Each product instance is separated from the instance of the original project, enabling both projects (original and imported) to operate independently without any interference.

#. Run the solution with the ``--portal`` option.
#. Click :guilabel:`Import project`.
#. Enter a display name for the project.
#. Select the ``.safx`` file to import.
#. Click :guilabel:`Import`.

SAF Portal automatically launches the Solution UI for the new project.

.. image:: /_static/images/projects_import_project.png
   :alt: Import project in SAF Portal

List projects
=============

To list all existing projects using SAF Portal, run the solution with the ``--portal`` option.

.. image:: /_static/images/projects_list_projects.png
  :alt: List projects in SAF Portal

Delete a project
================

To delete a project using SAF Portal:

#. Run the solution with the ``--portal`` option.
#. Find the project to delete, click the button for more options and click :guilabel:`Delete project`.
#. When asked for confirmation, click :guilabel:`Delete`.

.. image:: /_static/images/projects_delete_project.png
  :alt: Delete project in SAF Portal


Upgrade a project after modifying the solution
==============================================

After modifying the solution, you may need to upgrade the existing projects before you continue using them. You can do this using SAF Portal.

#. Run the solution with the ``--portal`` option.
#. Find the project to upgrade and click on it to open it.
#. When asked to confirm the migration, click :guilabel:`Migrate`.

The project is now upgraded and SAF Portal automatically redirects you to the Solution UI for the project.


Supported modifications
-----------------------

Project upgrade optional
~~~~~~~~~~~~~~~~~~~~~~~~~~

These modifications *do not* trigger an error if the project is used before being upgraded.

.. note::
  You are recommended to upgrade the project, nonetheless.

-	Modifying the solution display name
-	Modifying the solution version
-	Adding/removing transactions
-	Modifying the default value of a step field
-	Modifying the validator of a step field: only allowed if the current field value passes the new validator.
-	Modifying the signature of a transaction (function parameters and download/upload fields).

Project upgrade required
~~~~~~~~~~~~~~~~~~~~~~~~~~
These modifications *do* trigger an error if the project is used before being upgraded.

*	Adding/removing step fields
*	Adding/removing steps
*	Modifying the type of a step field (only allowed if the old and new types are casteable---for example, from ``int`` to ``float``)

.. note::
  Renaming a step or a step field is equivalent to removing the old one and adding a new one. Therefore, old values are not retained, and the new step or step field is initialized with its default values.

Unsupported modifications
--------------------------

These modifications render the project unusable. If made, the project cannot be upgraded and becomes inoperable.

-	Modifying the validator of a step field when the new one invalidates the current field value.
-	Modifying the type of a step field: if the current field value cannot be cast to the new type (for example, from ``str`` to ``int``).

Project Icons
=============

Project card icons are resolved using this order of precedence:

1. project.icon from the project payload
2. projectIconUrl from component properties
3. Bundled inline SVG fallback icon

If an external icon URL fails to load, the dashboard falls back to the bundled
inline SVG icon automatically.

.. code-block:: python

      return html.Div(
          [
              ansys_saf_projects_dashboard.ProjectsDashboard(
                  id="projects-dashboard",
                  apiBaseUrl=API_BASE_URL,
                  # solutionImageUrl='<my_path/assets/image.application.svg>',
                  # solutionDescription='My solution description...',
                  # Optional: point to a Project specific icon served by Dash
                  projectIconUrl="/assets/project.svg",
              ),
          ]
      )

The image container uses a responsive 16:9 aspect ratio.

.. rubric:: Default project placeholder

.. figure:: /_static/project-default-icon.png
    :width: 65%

.. rubric:: Custom project icon

.. figure:: /_static/project-custom-icon.png
    :width: 65%


Project files location
======================

By default, the project folder for storing the project files is created in :file:`%APPDATA%/ansys/glow/SOLUTION_NAME/project_files`.

You can change the location of the project files directory by setting the :envvar:`GLOW_PROJECT_FILES_DIRECTORY` environment variable. For example, the following code sample causes SAF GLOW Engine to store the project files  in ``D:/my_project_files/`` directory.

.. code-block::

  $env:GLOW_PROJECT_FILES_DIRECTORY="D:/my_project_files"

.. warning::
  Do not move or modify project files manually. Doing so may lead to data loss or unexpected behavior.
