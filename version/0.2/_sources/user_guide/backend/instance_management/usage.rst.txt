.. _instance_management_usage:

Usage
#####

Product instance management allows you to create an instance of an Ansys product (**product instance**) within a transaction method and then access the product instance across multiple transaction methods.
By keeping a product instance running and making it available to transaction methods, we avoid the expensive process of restarting and reinitializing a new instance for each method that needs to access a product instance.

The product instance is created in an isolated environment which is separate from the isolated environment where the transaction method executes.

The state of a product instance is saved after the execution of any transaction method that accesses the product instance so that its state can be restored at any point where the product instance has to be restarted. This happens when using a product instance after it has been shut down or killed, when the solution application or the product instance management system (either PIM or HPS) are restarted, or when importing a project.

A SAF GLOW Engine  solution interacts with a product instance through a :ref:`product instance manager <instance_management_supported_products>`.

The product instance manager can:

1. initialize and shutdown a product instance,

2. manage the files that the product instance might need to run its functionalities, and

3. persist information about the product instance and store its state to be able to recreate it when it is deleted.

On top of that, it incorporates a **product instance client** that is connected to the product instance and provides access to its functionalities.

.. _create-product-instance:

Create a product instance
=========================

It takes two steps to create a product instance:

1. decorating a transaction method with the ``create_instance`` decorator, which can be imported from ``ansys.saf.glow.solution``, and

2. initializing the product instance manager inside the decorated transaction method.

Decorate the transaction method
-------------------------------

The ``create_instance`` decorator takes a name for the product instance and a product instance manager class as required parameters. To use the product instance manager inside the transaction method, the transaction method needs to accept a parameter that fits the name and class of the product instance manager.

In the following example, ``maxwell_2d_instance`` is the name of the product instance manager and ``Maxwell2DManager`` is its class (imported from ``ansys.saf.product_manager.aedt``). Note that the transaction method accepts a parameters that fits the product instance manager.

.. code:: python

    @transaction(self=StepSpec(download=["aedt_version"]))
    @create_instance("maxwell_2d_instance", Maxwell2DManager)
    @long_running
    def initialize_maxwell_2d_instance(self, maxwell_2d_instance: Maxwell2DManager) -> None:
        maxwell_2d_instance.initialize(version=self.aedt_version)

The ``create_instance`` decorator accepts two other optional parameters: ``identifier``, which when given overwrites the name of the variable containing the product instance manager inside the transaction method.
The default value of ``identifier`` is the name of the product instance.
It is essential that unique values are explicitly applied to the ``identifier`` parameter when two or more product instances from different steps with the same name are required in a transaction method.
The other optional parameter is ``max_execution_time``, which sets the amount of time in seconds after which a product instance will be forcefully terminated by the product instance management system.
``max_execution_time`` is supported only by the ``HPS`` product instance management system. When using ``PIM``, the instance lasts as long as the PIM service is running, unless ``shutdown`` is called on that instance.
The PIM service will run indefinitely in an on-prem deployment or for the duration the solution application is running in a desktop deployment.

.. warning::

  If the product instance exceeds the maximum execution time, the instance will be forcefully terminated, even if it happens during a transaction. In this case, the instance will not be properly shut down by the product instance management system and the instance's state will not be stored properly.

.. warning::

  Every call to a method decorated with ``create_instance`` will create a new product process irrespective of state of any existing instance.
  Any existing instance assigned to the given name will be shutdown and replaced as part of the ``create_instance`` transaction method.
  Creating a new instance is resource intensive and will require a time noticeable to end users.
  Ensure that this behavior is taken into account when designing solutions.
  See :ref:`create_instance_best_practice`.

Initialize the product instance manager
---------------------------------------

As shown in the last example, the transaction method calls the product instance manager's ``initialize`` method.
This is mandatory to be able to use the Ansys product.
It is this initialization that starts a product instance, which will be available for use in later commands both in the same and in other transaction methods.

.. note::

  1. The transaction method can have code unrelated to the product instance manager before or after calling the ``initialize`` method. However, the product instance manager will only be functional after this call.

  2. Attempting to use an instance without initializing it leads to the following error message: ``The method has been called out of sequence.``

  3. The arguments to the ``initialize`` method will vary depending on the class of the product instance manager. Refer to the documentation of the specific :ref:`product instance manager <instance_management_supported_products>` you are using.

  4. If the ``initialize`` method is called a second time, the product instance is restarted and its previous state is lost.

  5. You don't need to re-create the instance after closing the solution. The instance will be resumed and available for use in later transaction methods after re-opening the project.

.. _access-use-product-instance:

Use a running product instance
==============================

To access an already running product instance from within a transaction method, we only need to decorate the transaction method with the ``instance`` decorator (imported from ``ansys.saf.glow.solution``).
This decorator just requires the name of the product instance, but it also has the ``identifier`` optional parameter.

To actually make use of the functionalities of the Ansys product, we need to use the product instance client, which is accessible through the product instance manager's ``instance`` property. It is mandatory to decorate the transaction method that uses this property with either the ``create_instance`` or the ``instance`` decorators.

In case the product instance is not already running, it is started in its last saved state when the property ``instance`` is used. The state of the product instance is saved at the end of every transaction method that creates or uses the product instance.

The following code is a simple example of accessing and executing a method on a product instance. In this example:

* The ``simulate`` method uses the ``maxwell_2d_instance`` product instance.
* The product instance client is accessed via the ``instance`` property of the product instance manager passed to the ``simulate`` method by the ``instance`` decorator.
* The ``simulate`` method calls the Ansys product's ``analysis`` method and then accesses its ``result`` property and saves its value in the ``result`` step field.

.. code:: python

    @transaction(self=StepSpec(upload=["result"]))
    @instance("maxwell_2d_instance")
    @long_running
    def simulate(self, maxwell_2d_instance: Maxwell2DManager) -> None:
        maxwell_2d_instance.instance.analysis()
        self.result = maxwell_2d_instance.instance.result

.. warning::

  On a given method, there should not be more than one ``create_instance`` or ``instance`` decorator referring to the same instance.

Shut down a product instance
============================

To shut down a product instance, you should use the product instance manager's ``shutdown`` method as show in the following example:

.. code:: python

    @transaction(self=StepSpec())
    @instance("maxwell_2d_instance")
    def shutdown_m2d(self, maxwell_2d_instance: Maxwell2DManager) -> None:
        maxwell_2d_instance.shutdown()

After shutting down the product instance, you cannot reuse the instance in another transaction method.
It is necessary to invoke a transaction method with the ``create_instance`` decorator if you need to use the instance in a following transaction method.

.. _create_instance_best_practice:

Best practice when using the ``@create_instance`` decorator
===================================================================================

The recommended best practice when using the ``@create_instance`` decorator, that ensures the API is invoked correctly
whilst providing a rapid response to the end user, is as follows:

1. Create a boolean field on the step where the instance is created and set it to ``False`` by default.
   The field should be associated with just one instance on the step.
   For example:

   .. code:: python

       class SomeStep(Step):
           some_instance_created: bool = False

2. Read the documentation for the product manager and the associated PyAnsys package that you are using.
   Determine the effect of the arguments to the ``initialize`` method called within the ``@create_instance`` method.
   Some the arguments to ``initialize`` cannot be overridden once the instance is created. For example it is typical
   for the ``version`` argument to determine the product executable used for the instance and hence it cannot be overridden
   via the PyAnsys API.  For the rest of this section we will divide the ``initialize`` arguments into "overridable properties"
   and "non-overridable properties."

   For each non-overridable property create a corresponding field in the step.
   For example:

   .. code:: python

        some_instance_current_version: str = "NOT SET"

   These fields are *in addition* to any fields used to capture the user's specification for the instance.
   For example to compliment the ``some_instance_current_version`` field there will probably be another field to capture
   the user's requested version for the instance as follows:

   .. code:: python

       some_instance_requested_version: str = "NOT SPECIFIED"

3. Ensure that the transaction method decorated with ``@create_instance`` has the following features:

    - contains a call to the product instance manager's ``initialize`` method
    - assigns ``True`` to the boolean field created in (1).
    - is decorated with ``@long_running``.
    - stores the values of the non-overridable properties of the instance into the fields created in (2)

   For example:

   .. code:: python

       @transaction(
           self=StepSpec(
               download=["some_instance_requested_version", "cad_file"],
               upload=["some_instance_created", "some_instance_current_version"],
           ),
           enable_termination_event=True,
       )
       @create_instance("some_instance", SomeManager)
       @long_running
       def create_some_instance(self, some_instance: SomeManager) -> None:
           some_instance.initialize(version=self.some_instance_requested_version, cad_file=self.cad_file)
           self.some_instance_created = True
           self.some_instance_current_version = self.some_instance_requested_version

   As the transaction method is long running the UI and backend need to coordinate the completion of instance activation. In the example
   code we use transaction termination events to achieve this.

4. Create a transaction method which is decorated with the ``@instance`` decorator with the same product instance name.
   This method does the following in order:

     - restart the instance if it is not already running;
     - if the instance was not running, reload into the instance the instance state that existed at the end of the last transaction method that used the instance; and
     - reset the instance into a known good starting state for the rest of the workflow whether or not the instance was running

   The ``@instance`` decorator achieves the restart and reload which can take time which is why the method is decorated with ``@long_running``.
   The code for resetting the state of the instance is contained in the body of the method.
   The code to reset the instance will vary depending on the product and the solution.

   The method should have the same overridable property arguments as the ``@create_instance`` method to enable it to reset the state correctly.

   For example, if we assume the instance ``open`` method resets the state of the instance for the solution then a viable implementation would be:

   .. code:: python

       @transaction(
           self=StepSpec(
               download=["cad_file"],
           ),
           enable_termination_event=True,
       )
       @instance("some_instance")
       @long_running
       def reset_some_instance(self, some_instance: SomeManager) -> None:
           input_file_path = some_instance.storage_scope.get_cached(self.cad_file)
           some_instance.instance.open(input_file_path)

   It is possible that the solution workflow does not require the product instance API to be called at all and the method body could just be ``pass``.

5. If the instance is shutdown then the method shutting down the instance should set the boolean step field to False.
   For example:

   .. code:: python

       @transaction(self=StepSpec(upload=["some_instance_created"]))
       @instance("some_instance")
       def shutdown_some_instance(self, some_instance: SomeManager) -> None:
           some_instance.shutdown()
           self.some_instance_created = False

6. In the UI callback that initializes the product instance the code should determine if the transaction method decorated with ``@create_instance``
   has been called for the current project and if the required non-overridable property values have not changed.
   If not then that method is called, otherwise the method with the ``@instance`` decorator is called.
   For example:

   .. code:: python

       @callback(
           Input("initialize-button", "n_clicks"),
           Output("initialize-button", "disabled", allow_duplicate=True),
           State("url", "pathname"),
           prevent_initial_call=True,
       )
       def start_initializing_some_instance(n_clicks, project: MySolution):
           """Initialize with proper instance management."""
           # Get the current project and step
           step = project.steps.meshing_step

           # Determine whether the instance has even been created in this project
           if step.some_instance_created and step.some_instance_current_version == step.some_instance_requested_version:
               # If in a new session reactivate and reset the instance otherwise just reset the existing instance
               # reactivation takes time (non-blocking long running method)
               step.reset_some_instance()
           else:
               # create the instance, this will take time, (non-blocking long running method)
               step.create_some_instance()
           return True  # deactivate the initialize-button whilst the instance is being created

7. The UI and Backend need to coordinate the completion of instance activation. There is no single way to do this and the details will
   depend on the solution. The following code shows how the termination events can be used to achieve this:

   .. code:: python

       @callback(
           Input("create_some_instance_ws", "message"),
           Input("reset_some_instance_ws", "message"),
           Output("initialize-button", "disabled", allow_duplicate=True),
           State("url", "pathname"),
           prevent_initial_call=True,
       )
       def end_initializing_some_instance(create_message, reset_message, pathname):
           """Reconfigure UI after instance creation has completed."""
           return False  # reactivate the initialize-button

   The UI layout method for the method will need to declare the event streams for the transaction methods so continuing the example
   to include a viable layout function for the step:

   .. code:: python

       def layout(step: SomeStep):
           running = (
               step.get_method_state("create_some_instance").status == MethodStatus.Running
               or step.get_method_state("reset_some_instance").status == MethodStatus.Running
           )
           return html.Div(
               [
                   html.Button("Initialize", id="initialize-button", disabled=running),
                   DashClient.create_event_listener(step, stream_name="create_some_instance", id="create_some_instance_ws"),
                   DashClient.create_event_listener(step, stream_name="reset_some_instance", id="reset_some_instance_ws"),
               ]
           )

   Obviously the user experience of this example is very crude (the only indication that something is happening is that the button is disabled)
   but the code here shows the basic principles.

8. The solution may make calls to transaction methods decorated with ``@instance`` conditional on ``step.some_instance_created`` to avoid
   errors. The SAF infrastructure raises errors on calls to ``@instance`` methods if a corresponding ``@creating_instance`` method has not been called.

.. _project-instance-files:

Manage product instance files
=============================

.. note::

  Using the manager file methods described below requires the initialization of the product instance manager through its ``initialize`` method.

.. important::

  Make sure your code is not dependent on the actual location of the product instance. Otherwise, it will break with redeployment.

.. tab-set::

    .. tab-item:: EntityHandle

        SAF GLOW Engine  provides access to the storage scopes of the transaction method and the product instance.

        - Use the ``self.storage_scope`` property to access the transaction method's storage scope.
        - Use the product instance manager's ``storage_scope`` property to access the product instance's storage scope. For example, for retrieving the path of a file in a form that is accessible to the product instance using ``get_cached``.

        .. code:: python

            class TestStep(StepModel):
                maxwell_project: EntityHandle = NO_ENTITY
                input_data: EntityHandle = NO_ENTITY
                output_data: EntityHandle = NO_ENTITY

                @transaction(self=StepSpec(download=["maxwell_project"]))
                @create_instance("m2d_inst", Maxwell2DManager)
                @long_running
                def create(self, m2d_inst: Maxwell2DManager) -> None:
                    m2d_inst.initialize(project_file=self.maxwell_project)

                @transaction(self=StepSpec(download=["input_data"], upload=["output_data"]))
                @instance("m2d_inst")
                @long_running
                def simulate(self, m2d_inst: Maxwell2DManager) -> None:
                    # get_cached already raises error if input_data is not found
                    input_data_path_from_maxwell = m2d_inst.storage_scope.get_cached(self.input_data)
                    output_csv = m2d_inst.storage_scope.get_storage_root() / "output.csv"
                    m2d_inst.instance.simulate(input_data_path_from_maxwell, str(output_csv))
                    self.output_data = m2d_inst.storage_scope.store(output_csv)

        Note that, when using BDM, you can access stored entity handles from both storage scopes. For this reason, the entity handle referenced by ``self.input_data`` doesn't have to be uploaded from transaction to product instance. Similarly, ``self.output_data`` at the end of the transaction doesn't have to be copied back to the transaction. However, when passing file paths to the product instance, you must use the product instance's storage scope (``m2d_inst.storage_scope``) to ensure the paths are accessible to the product. The transaction's storage scope (``self.storage_scope``) should only be used for operations within the transaction method itself. For example, you could also modify the transaction to read the output data using the transaction's storage scope:

        .. code:: python

            @transaction(self=StepSpec(download=["input_data"], upload=["output_data_content"]))
            @instance("m2d_inst")
            @long_running
            def simulate(self, m2d_inst: Maxwell2DManager) -> None:
                # get_cached already raises error if input_data is not found
                input_data_path_from_maxwell = m2d_inst.storage_scope.get_cached(self.input_data)
                output_csv = m2d_inst.storage_scope.get_storage_root() / "output.csv"
                m2d_inst.instance.simulate(input_data_path_from_maxwell, str(output_csv))
                output_data = m2d_inst.storage_scope.store(output_csv)
                self.output_data_content = self.storage_scope.get_text(output_data)


Product instance state files
----------------------------

The product instances usually store their state and output files in a protected location within the file system called the ``state directory``.
This directory has the same lifespan as the product instance. This means that when the product instance is shutdown, the ``state directory`` and all its contents are also deleted.
In case you need to persist some state/output files beyond the lifespan of the product instance, you need to store them as ``EntityHandle`` using the product storage scope's ``store_from_state_directory`` method.

.. code:: python

    class TestStep(StepModel):

        state_entity_handle: EntityHandle = NO_ENTITY

        @transaction(self=StepSpec(upload=["state_entity_handle"]))
        @instance("my_product_instance")
        def store_from_product_state_dir(
            self,
            my_product_instance: MyProductInstanceManager,
        ) -> None:
            filepath_from_product = my_product_instance.state_directory / "project.txt"
            self.state_entity_handle = my_product_instance.storage_scope.store_from_state_directory(filepath_from_product)


.. _other-step-instance:

Referring to an instance on another step
========================================

It is possible to refer to a product instance created on another step from a transaction method.
The first argument of the ``instance`` decorator can contain a period character where the part before
the period is a step name and the part after the period is the name of a product instance on the named step.
A decorator of this form allows the transaction method to access the product instance created on the named step.
The name of a step is the field name of the step on the ``StepsModel`` derived class defining the solution steps.

For example consider the following solution:

.. code:: python

    class SimulationSetupStep(StepModel):
        aedt_version: str = "2023 R2"

        @transaction(self=StepSpec(download=["aedt_version"]))
        @create_instance("maxwell_2d_instance", Maxwell2DManager)
        @long_running
        def initialize_maxwell_2d_instance(self, maxwell_2d_instance: Maxwell2DManager) -> None:
            maxwell_2d_instance.initialize(version=self.aedt_version)


    class SimulationStep(StepModel):

        result: str = ""

        @transaction(self=StepSpec(upload=["result"]))
        @instance("simulation_setup.maxwell_2d_instance")
        @long_running
        def simulate(self, maxwell_2d_instance: Maxwell2DManager) -> None:
            maxwell_2d_instance.instance.analysis()
            self.result = maxwell_2d_instance.instance.result


    class Steps(StepsModel):
        simulation_setup: SimulationSetupStep
        simulation: SimulationStep


    class MySolution(Solution):
        display_name: str = "My Solution"
        steps: Steps

In this example the ``simulate`` method uses a product instance named ``maxwell_2d_instance`` created on the step named ``simulation_setup``.

.. _unshared-product:

Use an unshared product instance
====================================

There may be cases where the Ansys product is only used within a single transaction.
It is possible to create an *unshared* product instance that is not persisted beyond the transaction method where it is created.
Using an unshared product instance avoids the overhead of dealing with the ``@create_instance`` and ``@instance`` decorators as well as the product instance manager's state persistence.
To create an unshared product instance within a transaction, simply instantiate the product instance manager using the ``with`` keyword.

.. code:: python

    class UnsharedAedtStep(StepModel):
        aedt_version: str = "2025 R2"
        result: str = ""

        @transaction(self=StepSpec(download=["aedt_version"], upload=["result"]))
        @long_running
        def simulate(self) -> None:
            with Maxwell2DManager(version=self.aedt_version) as maxwell_2d_instance:
                maxwell_2d_instance.instance.analysis()
                self.result = maxwell_2d_instance.instance.result

In this example, the ``simulate`` method creates an unshared product instance of ``Maxwell2DManager``.
The product instance is only available within the ``with`` block and is automatically shut down when exiting the block.
The parameters required to instantiate the product instance manager are the same as those required by the product instance manager's ``initialize`` method.

.. note::
   Using unshared product instances is the recommended approach when the product is only needed within a single transaction method.
   You may be tempted to use ``PyAnsys`` libraries directly instead, but using unshared product instances ensures proper integration with the SAF GLOW Engine  solution framework.
   In addition to that, it also offers various benefits:
   - Consistent semantics with all products used within SAF GLOW Engine  solutions.
   - Easier future migration to shared product instances if needed.
   - Lifetime management of the product instance: no need to write code to explicitly start and stop the product instance.
   - Ensures that the product instance is properly shut down after use: preventing resource leaks.
   - Deployment agnostic: works seamlessly whether the solution is deployed locally or on the cloud.

