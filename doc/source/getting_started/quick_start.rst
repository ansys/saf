.. _quick_start_guide:

Quick-start guide
#################

Follow these instructions to quickly create, set up, and run a minimal SAF-based solution.
You can use either the :program:`SAF CLI` tool or the :program:`Solutions Manager` VS Code extension.

Create a solution
=================

.. tab-set::

    .. tab-item:: SAF CLI

        Create a solution using SAF CLI:

        #. Instantiate the solution template:

           .. code-block:: bash

               saf new

        #. When prompted, provide the following values, pressing :kbd:`Enter`
           to select the default value or to validate non-default values provided.

           a. Enter a solution name.

              You can use the default option (``my-solution``) or provide a custom one.

           b. Enter a solution display name.

              You can use the default option (``My Solution``) or provide a custom one.

           c. Specify the UI framework.

              You can use the default option (``dash``) or select ``none``.

           d. Enter the solution namespace.

              You can use the default option (``saf.solutions``) or provide a custom one.

        A directory with the solution name is created in the current directory.

    .. tab-item:: Solutions Manager

      Create a solution using Solutions Manager:

      #. Open Visual Studio Code.

      #. In the Activity Bar, click the **Solutions Manager** icon.

      #. In the **Solutions Manager**  pane, expand the **Create Solution** view.

         .. image:: /_static/images/solutions_manager_create_solution_view.png
            :alt: Solutions Manager Create Solution view
            :width: 45%

      #. Provide the following values:

         a. Enter a solution name.

            You can use the default name (``my-solution``) or provide a custom one.

         b. Enter a solution display name.

            This value is automatically generated based on the solution name (``My Solution``). You can modify it as needed.

         c. Select the UI framework.

            Select a framework to use for the solution.

         d. Enter the solution namespace.

            Enter the namespace to use for the solution.

         e. Enter the target directory.

            Enter the directory where the solution will be saved.

      #. Generate the solution.

         Click the :guilabel:`Create solution` button. Alternatively, you can copy the command under **Create solution command** and run it in the terminal.

      A directory with the solution name is created in the target directory.

The solution generated from the template is a simple two-step, three-page solution.

.. seealso::

   For more detailed information, see :ref:`ug-scaffold-create-solution` in the :ref:`user_guide`.


Install the solution
=====================

.. tab-set::

    .. tab-item:: SAF CLI

      Install the solution using SAF CLI:

      #. Change to the solution's root directory:

         .. code-block:: bash

          cd <solution_name>

      #. Install the solution's development environment:

         .. code-block:: bash

          saf install -f

    .. tab-item:: Solutions Manager

      Install the solution using Solutions Manager:

      .. note::

         These instructions assume that VS Code is already open.

      #. In the **Solutions Manager**  pane, expand the **Setup Solution** view.

         .. image:: /_static/images/solutions_manager_setup_solution_view.png
            :alt: Solutions Manager Setup Solution view
            :width: 45%

      #. Provide the following values:

         a. Select the solution you want to install.

            You can either select an option from the list of available solutions or browse for the solution folder of a different one.

         b. Select an environment cleanup option.

            You can either use the default option (**No clean-up**) or select a different one.

      #. Set up the environment.

         Click the :guilabel:`Setup solution environment` button. Alternatively, you can copy the command under **Solution setup command** and run it in the terminal.

The installation installs all necessary dependencies. You can monitor its progress in the terminal.

.. seealso::

   For more detailed information, see :ref:`ug-install` in the :ref:`user_guide`.


Run the solution
================

You can open the solution in a :ref:`desktop window <quick-run-desktop>` , a :ref:`web browser <quick-run-web-browser>` , or the :ref:`SAF Portal <quick-run-saf-portal>`, which
provides a project management interface for the solution.


.. seealso::

   For more detailed information, see :ref:`user_guide_run_on_desktop` in the :ref:`user_guide`. This section covers concepts that are generally applicable to all three SAF run modes.


.. _quick-run-desktop:

Run the solution in a desktop window
-------------------------------------

.. tab-set::

    .. tab-item:: SAF CLI

      Run the solution in a desktop window using SAF CLI:

      .. code-block:: bash

        saf run

    .. tab-item:: Solutions Manager

      .. note::

         These instructions assume that VS Code is already open.

      Run the solution in a desktop window using Solutions Manager:

      #. In the **Solutions Manager**  pane, expand the **Run Solution** view.

         .. image:: /_static/images/solutions_manager_run_solution_view_desktop.png
            :alt: Solutions Manager Run Solution in desktop view
            :width: 35%

      #. Provide the following values:

         a. Select the solution you want to run.

            You can either select an option from the list of available solutions or browse for the solution folder of a different one.

         b. Select your run options:

            Ensure that **Portal mode** and **Browser mode** are not selected.

         c. Select a log level:

            The default log level is **INFO**. You can select a different log level if needed.

         d. Enter a project name.

            Enter the name of the project you want to run.

         e. Specify the solution environment.

            Click the :guilabel:`Configure solution environment` button to open the **SAF Environment Configuration** interface in the VS Code editor. Alternatively, you can browse to an environment (``.env``) file.

            .. image:: /_static/images/getting_started_quick_start_solutions_manager_saf_environ_config_page.png
               :alt: Solutions Manager SAF Environment Configuration page
               :width: 75%

         f. Modify **SAF Environment Configuration** settings as needed and click the :guilabel:`Save Configuration` button.

      #. Run the solution.

         Click the :guilabel:`Run solution` button. Alternatively, you can copy the command under **Solution run command** and run it in the terminal.

The solution UI opens in a desktop window.

.. image:: /_static/images/getting_started_quick_start_minimal_solution_intro_page.png
   :alt: Solution opened in a desktop window

.. _quick-run-web-browser:

Run the solution in a web browser
---------------------------------

.. tab-set::

    .. tab-item:: SAF CLI

      Run the solution in a web browser using SAF CLI:

      .. code-block:: bash

        saf run --browser

    .. tab-item:: Solutions Manager

      Run the solution in a web browser using Solutions Manager:

      .. note::

         These instructions assume that VS Code is already open.

      #. In the **Solutions Manager**  pane, expand the **Run Solution** view.

         .. image:: /_static/images/solutions_manager_run_solution_view_browser.png
            :alt: Solutions Manager Run Solution in browser view
            :width: 45%

      #. Provide the following values:

         a. Select the solution you want to install.

            You can either select an option from the list of available solutions or browse for the solution folder of a different one.

         b. Select your run options:

            Ensure that **Browser mode** is selected.

         c. Select a log level:

            The default log level is **INFO**. You can select a different log level if needed.

         d. Enter a project name.

            Ener the name of the project you want to run.

         e. Specify the solution environment.

            Click the :guilabel:`Configure solution environment` button to open the **SAF Environment Configuration** interface in the VS Code editor. Alternatively, you can browse to an environment (``.env``) file.

            .. image:: /_static/images/getting_started_quick_start_solutions_manager_saf_environ_config_page.png
               :alt: Solutions Manager SAF Environment Configuration page
               :width: 85%

         f. Modify **SAF Environment Configuration** settings as needed and click the :guilabel:`Save Configuration` button.

      #. Run the solution.

         Click the :guilabel:`Run solution` button. Alternatively, you can copy the command under **Solution run command** and run it in the terminal.

The solution UI opens in a web browser window.

.. image:: /_static/images/minimal_solution_intro_page_browser.png
   :alt: Solution opened in a browser window


.. _quick-run-saf-portal:

Run the solution from SAF Portal
------------------------------------

.. tab-set::

    .. tab-item:: SAF CLI

      Run the solution from SAF Portal using SAF CLI:

      .. code-block:: bash

        saf run --portal

    .. tab-item:: Solutions Manager

      Run the solution from SAF Portal using Solutions Manager:

      .. note::

         These instructions assume that VS Code is already open.

      #. In the **Solutions Manager**  pane, expand the **Run Solution** view.

         .. image:: /_static/images/solutions_manager_run_solution_view_portal.png
            :alt: Solutions Manager Run Solution in SAF Portal view
            :width: 45%

      #. Provide the following values:

         a. Select the solution you want to install.

            You can either select an option from the list of available solutions or browse for the solution folder of a different one.

         b. Select your run options:

            Ensure that **SAF Portal mode** is selected.

         c. Select a log level:

            The default log level is **INFO**. You can select a different log level if needed.

         d. Enter a project name.

            Ener the name of the project you want to run.

         e. Specify the solution environment.

            Click the :guilabel:`Configure solution environment` button to open the **SAF Environment Configuration** interface in the VS Code editor. Alternatively, you can browse to an environment (``.env``) file.

            .. image:: /_static/images/getting_started_quick_start_solutions_manager_saf_environ_config_page.png
               :alt: Solutions Manager SAF Environment Configuration page

         f. Modify **SAF Environment Configuration** settings as needed and click the :guilabel:`Save Configuration` button.

      #. Run the solution.

         Click the :guilabel:`Run solution` button. Alternatively, you can copy the command under **Solution run command** and run it in the terminal.

The solution opens in the SAF Portal user interface. SAF Portal provides a project management interface for the solution, allowing you to create new projects, view existing projects, and manage project settings.

.. image:: /_static/images/minimal_solution_projects_dashboard_ui_empty.png
   :alt: Solution opened in SAF Portal



