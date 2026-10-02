.. _add_step:

Add steps
##########

Steps are the building blocks of a solution workflow. Each step represents a distinct phase in the solution's process flow, typically with its own UI and functionality. You can add steps to extend functionality without modifying the solution structure.

.. rubric:: When to add a step

* Your solution workflow needs additional logical phases
* You want to break a complex process into smaller parts
* You're extending an existing solution with new capabilities


Add a step
===========

You can add a step to your solution using either SAF CLI or Solutions Manager.

.. tab-set::

  .. tab-item:: SAF CLI

    Add a step to the solution using SAF CLI:

    #. Run the following command:

       .. code-block:: text

         saf add-step <solution-name>

    #. When prompted, provide the following values, pressing :kbd:`Enter` to select the default value
       or to validate non-default values provided.

       a. Enter the name for the step.

          Make sure it follows the rules described in :ref:`user_guide_step_naming_conventions`.

       b. Select a UI framework.

          .. warning::

            You must use the same UI framework for all steps in a solution. If you try to add a step with a different UI framework than the one used to create the solution, the command returns an error.

            You can add steps without a UI framework by selecting ``none`` for any solution, regardless of its UI framework.

       c. Select a step template (optional).

    The new step is created and integrated into your solution. Files are created and modified as described in :ref:`user_guide_add_step_files_output`.

  .. tab-item:: Solutions Manager

    Add a step to the solution using Solutions Manager:

    #. Open Visual Studio Code.

    #. In the Activity Bar, click the **Solutions Manager** icon.

    #. In the **Solutions Manager** pane, expand the **Customize Solution** view.

       .. image:: /_static/images/solutions_manager_customize_solution_view.png
         :alt: Solutions Manager Customize Solution view
         :width: 45%

    #. Under **Add step**, provide the following values:

       a. Select the solution where you want to add a step.

          You can either select an option from the list of available solutions or browse for the solution folder of a different one.

       b. Enter the name for the step.

          Make sure it follows the rules described in :ref:`user_guide_step_naming_conventions`.

       c. Select the UI framework.

          .. warning::

            You must use the same UI framework for all steps in a solution. If you try to add a step with a different UI framework than the one used to create the solution, the command returns an error.

            You can add steps without a UI framework by selecting ``none`` for any solution, regardless of its UI framework.

       d. Enter the namespace to use for the solution.

       e. Enter the target directory where the solution will be saved.

    #. Create the step.

       Click the :guilabel:`Add step` button. Alternatively, you can copy the command under **Add step command** and run it in the terminal.

When you open the solution, the new step will be visible in the left navigation panel.

.. seealso::

  For more information on available command-line options, see :ref:`user_guide_add_step_command_options`.


.. _user_guide_step_naming_conventions:

Step naming conventions
--------------------------

Make sure your step name follows these conventions:

* A step name cannot be a path.
* A step name cannot contain:

  * Forward-slash (``/``) or backward-slash (``\``) characters
  * Invalid characters: colons (``:``), semi-colons (``;``), asterisks (``*``), question marks (``?``), or angle quotations (``<``, ``>``)

The ``saf add-step`` command
------------------------------

The ``saf add-step`` command is used to add a new step to an existing solution. It integrates the step into the solution's structure, creating necessary files and updating existing ones as described in the previous section.



.. _user_guide_add_step_command_options:

``saf add-step`` options
------------------------------

The ``saf add-step`` command has multiple options. To see them all, run the following command:

.. code-block:: bash

    saf add-step --help

The following ``saf add-step`` options are available:

.. list-table::
   :header-rows: 1
   :stub-columns: 1
   :widths: 25 75

   * - Option
     - Description

   * - ``--step-name``
     - The name of the step to add to the solution.

   * - ``--ui-framework [dash|none]``
     - Type of solution UI.

   * - ``--template <template-name>``
     - The name of the step template to use.

       For more information, see :ref:`step_templates`.

.. note::

  Setting these options disables their command prompt.


.. _user_guide_add_step_files_output:

``saf add-step`` output
------------------------------

Adding a step generates new files and modifies existing files in the solution.

Generated files
~~~~~~~~~~~~~~~~

The following files are generated:

.. code-block:: text
  :emphasize-lines: 7, 10

  <solution-name>/
  ├───src
  │   └───ansys
  │       └───solutions
  │           └───<solution_module>
  │               ├───solution
  │               │   │   my_minimal_step.py # (new)
  │               └───ui
  │                   └───pages
  │                           my_minimal_page.py # (new)

Modified files
~~~~~~~~~~~~~~

The following files are modified accordingly:

.. code-block:: text
  :emphasize-lines: 7, 10

  <solution-name>/
  ├───src
  │   └───ansys
  │       └───solutions
  │           └───<solution_module>
  │               ├───solution
  │               │   │   definition.py # (edited)
  │               └───ui
  │                   └───pages
  │                           page.py # (edited)

.. tabs::

    .. code-tab:: python
       :caption: definition.py

       # Added a new import and new step to the class.
       from ansys.solutions.<solution_module>.solution.my_minimal_step import MyMinimalStep

       class Steps(StepsModel):

           my_minimal_step: MyMinimalStep

    .. code-tab:: python
       :caption: page.py

       # Added a new step to the array.
       page_list = [
           {
               "id": "my_minimal_page",
               "text": "My Minimal Step",
               "prefixIcon": "carbon:ibm-engineering-workflow-mgmt",
               "expanded": True,
           },
       ]

       # This block is inserted under the function display_page(pathname, value):
       elif value["index"] == "my_minimal_page":
           return my_minimal_page.layout(project.steps.my_minimal_step)







.. _step_templates:

Use step templates
===================

SAF ships a collection of built-in step templates that generate ready-to-use solution
steps. Instead of writing boilerplate code from scratch, you can scaffold common
patterns (calculator, HPS job submission, product instance management) and then
customize them to fit your use case.


Prerequisites
---------------

Before using step templates, ensure you've met the following prerequisites:

.. list-table::
  :header-rows: 1
  :stub-columns: 1
  :widths: 20 80

  * - Prerequisite
    - Description

  * - SAF Templates
    - Version 4.0.1 or later.

      Using previous versions of the ``ansys-saf-templates`` package might produce unexpected results or errors when attempting to add a step.

  * - SAF CLI
    - Version 4.0.1 or later.

  * - Shared Technology Components (STC)
    - Some templates require a deployment of Ansys HPC Platform Services (HPS).

  * - Ansys products
    - Depending on the template you intend to use, the corresponding Ansys product must be
      installed and licensed on your machine (for example, AEDT, Mechanical, MAPDL, Fluent, Geometry).

.. attention::

  Step templates are available in SAF CLI version 4.0.1 or later. If you are using an earlier version,
  you can still add a step to a solution, but you will need to implement the step logic and UI from scratch.

  To manually install a newer version of the SAF Templates package, run the following command in the Python environment where SAF CLI is installed:

  .. code-block:: bash

    pip install ansys-saf-templates


Add a step from a template
----------------------------

Add a new step from a template by running the ``saf add-step`` command with the ``--template`` option:

.. code-block:: bash

    saf add-step <my_solution> --template <template_name>

If ``--template`` is omitted, the CLI interactively guides you through selecting a
template and the rest of the required parameters. You can also pass all information
as command-line arguments:

.. code-block:: bash

    saf add-step <my_solution> --step-name <step_name> --ui-framework <ui_framework> --template <template_name>


List available templates
-------------------------

You can list the available templates by running:

.. code-block:: bash

    saf templates

This shows all the templates available in ``ansys-saf-templates``, as well as any
additional templates from installed plugins. For information on available templates, see :ref:`user_guide_add_step_template_gallery`.


.. _user_guide_add_step_template_gallery:

Step template gallery
----------------------

.. list-table::
  :header-rows: 1
  :widths: 25 45 20 10

  * - Template
    - Description
    - Dependencies
    - Owner
  * - ``calculator-step``
    - A step that performs calculator operations. Useful as a starting point or
      reference for simple computation steps.
    - None
    - SAF SDK
  * - ``hps-simple-job-step``
    - A step that submits a simple job to Ansys HPC Platform Services (HPS).
      Generates the boilerplate for job submission, status polling, and result
      retrieval.
    - ``ansys-saf-sdk[core-hps]``, ``dash-iconify``
    - SAF SDK
  * - ``hps-parametric-study-step``
    - A step that runs a parametric study on HPS. Extends the simple job step
      with parameter sweeps and result aggregation.
    - ``ansys-saf-sdk[core-hps]``, ``dash-iconify``
    - SAF SDK
  * - ``instance-mgmt-geometry-step``
    - A step for basic Geometry instance management. Handles starting,
      connecting to, and stopping a Geometry service instance.
    - ``ansys-saf-sdk[instance-management-geometry]``
    - SAF SDK

Calculator
~~~~~~~~~~~~~~~~~~~~~

A minimal step template that performs basic calculator operations. This template
is ideal for learning how SAF step templates are structured or as a starting
point for custom computation steps that do not require external Ansys products.

**Generated files:**

- ``solution/<step_module_name>.py`` — Step model with calculator logic.
- ``ui/pages/<page_file_name>.py`` — UI page for interacting with the step.

HPS simple job
~~~~~~~~~~~~~~~~~~~~~~~

A step template that submits a single job to Ansys HPC Platform Services (HPS).
It provides the scaffolding for defining job parameters, submitting the job,
monitoring its status, and retrieving results.

**Prerequisites:** Access to an HPS deployment.

**Generated files:**

- ``solution/<step_module_name>.py`` — Step model with HPS job submission logic.
- ``solution/scripts/<step_module_name>_calculate_sum_simple.py`` — Script executed by the HPS job.
- ``ui/pages/<page_file_name>.py`` — UI page for configuring and monitoring the job.

HPS parametric study
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A step template that runs a parametric study on HPS. It builds on the simple job
step by adding support for defining parameter ranges, launching multiple jobs,
and aggregating results.

**Prerequisites:** Access to an HPS deployment.

**Generated files:**

- ``solution/<step_module_name>.py`` — Step model with parametric study logic.
- ``solution/scripts/<step_module_name>_calculate_sum.py`` — Script executed by each HPS job.
- ``ui/pages/<page_file_name>.py`` — UI page for configuring parameters and viewing results.

Geometry instance management
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A step template for managing Geometry service instances. It handles starting a
Geometry service, connecting to it, and cleaning up the instance when the step
completes.

**Prerequisites:** Ansys Geometry Service.

**Generated files:**

- ``solution/<step_module_name>.py`` — Step model with instance management logic.
- ``ui/pages/<page_file_name>.py`` — UI page for instance status and control.
