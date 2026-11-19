.. _prerequisites_solutions_manager:

Solutions Manager
#################

The SAF SDK framework includes a Visual Studio Code extension called :program:`Solutions Manager`. This extension provides a user-friendly interface for creating and managing solutions, configuring dependencies and environments, and running solutions directly from VS Code.

During the solution creation process, Solutions Manager:

* Automatically installs the ``ansys-saf-cli`` package in the VS Code environment.
* Manages solution lifecycle operations through ``ansys-saf-cli`` behind the scenes, eliminating the need for direct command-line interaction.
* Provides an integrated, visual workflow within VS Code, offering a more streamlined and user-friendly experience than using the command-line interface alone.


Installation
============

To download and install the Solutions Manager extension:

#. Download the ``solutions-manager-extension-v*.*.*.vsix`` file for the desired release from the `Releases <https://github.com/ansys/saf/releases?q=solutions-manager&expanded=true>`_ page.

#. Open VS Code.

#. Open the **Extensions** view by:

   * Clicking the **Extensions** icon in the Activity Bar, or
   * Pressing :kbd:`Ctrl+Shift+X`.

#. In the **Extensions** view, click the **More actions** (three-dot) menu in the top right corner and select :menuselection:`Install from VSIX`.

   .. image:: /_static/images/install_extension_vsix.png
      :alt: Install from VSIX option in the Extensions view
      :width: 65%

#. Browse to the downloaded ``solutions-manager-extension-v*.*.*.vsix`` file, select it, and click :guilabel:`Install`.

After the installation is complete, the Solutions Manager automatically installs ``ansys-saf-cli`` and configures the required environment. You can now begin creating and managing SAF solutions directly from VS Code.


Customization of view visibility
=================================

You can customize which Solutions Manager views are visible in Visual Studio Code.


Available solutions view
-------------------------

By default, the **Available Solutions** view is visible in the **Solutions Manager** pane. You can control its visibility using either of the methods in the following sections.

.. image:: /_static/images/solutions_manager_available_solutions_view_visibility.png
   :alt: Available solutions view visible in Solutions Manager
   :width: 50%

.. note::
   Currently, you can customize the visibility of only the **Available Solutions** view.


Method 1: Use VS Code settings
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#. Open VS Code Settings:

   * Press :kbd:`Ctrl+,` (Windows/Linux) or :kbd:`Cmd+,` (macOS).
   * Or use :menuselection:`File → Preferences → Settings`.

#. In the search bar, type ``Solutions Manager``.

#. Find the Solutions Manager extension settings.

#. Toggle the checkboxes to show or hide the view.

   .. image:: /_static/images/solutions_manager_pane_visibility_settings.png
      :alt: Solutions Manager settings in VS Code
      :width: 85%


Method 2: Settings JSON
~~~~~~~~~~~~~~~~~~~~~~~~

#. Open your VS Code user settings JSON file:

   a. Press :kbd:`Ctrl+Shift+P` (Windows/Linux) or :kbd:`Cmd+Shift+P` (macOS) to open the Command Palette.
   b. Type ``Preferences: Open User Settings (JSON)`` and select it.

   .. note::
      Depending on your VS Code version, this command may appear as ``Preferences: Open Settings (JSON)`` or ``Open User Settings (JSON)``. Use the command that opens the user settings file, not a workspace settings file.

#. Add the following entry to the existing top-level settings JSON object (do not overwrite other settings):

   .. code-block:: json

      {
        "solutions-init.enableSolutionsList": false
      }

#. Set the value to ``true`` to show the view or ``false`` to hide it.

   Use ``Preferences: Open Workspace Settings (JSON)`` if you want to apply this setting only to the current workspace.