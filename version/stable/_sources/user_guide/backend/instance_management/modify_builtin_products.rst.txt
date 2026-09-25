.. _instance_management_modify_builtin_products:

Modify built-in product configurations
######################################

SAF GLOW Engine  provides built-in configurations for Ansys products like optiSLang, Fluent, and Mechanical. However, you may need to customize these configurations for specific use cases. This includes modifying command line arguments, extending support to additional product versions, or setting custom environment variables.

To customize built-in product configurations, you need to:

1. Create custom product configuration classes that inherit from the built-in ones
2. Create custom product instance manager classes that inherit from the built-in ones and that use your new configurations
3. Use the new custom managers in your solution steps

This section demonstrates this process using optiSLang as an example.


Create custom configurations that modify the built-in ones
==========================================================

Look for the product configuration classes in the ``ansys.saf.product_configuration`` module for the product to modify.

For example:

.. code-block:: python

    from ansys.saf.product_configuration.optislang import (
        OptislangInstanceVersionConfiguration,
        OptislangInstanceConfiguration,
    )

Create a python file and put it inside a directory called ``product_instance_configs`` in the solution directory alongside the ``solution`` and ``ui`` directories. For example:

.. code-block:: console

    > tree .\src\ansys\solutions\my_solution\product_instance_configs
    .
    └── custom_optislang_config.py

In this file, you need to implement 2 classes:

- A class that inherits from ``OptislangInstanceVersionConfiguration`` and overrides only what is needed: command arguments, environment variables, etc.
- A class that inherits from ``OptislangInstanceConfiguration`` and overrides the ``get_version_configuration`` property to return your custom version configuration class and set a new ``product_name``. You can also modify the supported product ``versions`` property.

.. code-block:: python

    import tempfile
    from pathlib import Path

    from ansys.saf.product_configuration.optislang import (
        OptislangInstanceVersionConfiguration,
        OptislangInstanceConfiguration,
    )
    from ansys.saf.product_configuration.interfaces import IProductInstanceVersionConfiguration


    class CustomOptislangInstanceVersionConfiguration(OptislangInstanceVersionConfiguration):

        @property
        def execution_command(self) -> str:
            project_file = Path(tempfile.gettempdir()) / "_osl_project.opf"
            return (
                "${EXECUTABLE} --batch --enable-tcp-server ${PORT} --no-save "
                f"--no-run --force --new {project_file.as_posix()} --my-custom-args"
            )


    class CustomOptislangInstanceConfiguration(OptislangInstanceConfiguration):

        @property
        def product_name(self) -> str:
            return "custom-optislang"

        def get_version_configuration(self, version: str) -> IProductInstanceVersionConfiguration:
            return CustomOptislangInstanceVersionConfiguration(version)


.. warning::

   Product names must use only lowercase letters and hyphens, for safety. Uppercase letters in product names can cause failures in Product Instance Management Systems.


Create custom product managers that launch the new custom configurations
========================================================================

Look for the product instance manager classes in the ``ansys.saf.product_manager`` module for the product to modify.

.. code-block:: python

    from ansys.saf.product_manager.optislang import OptislangManager, InternalOptislangManager

Create a python file and put it inside the ``solution`` directory, alongside the step files. For example:

.. code-block:: console

    > tree .\src\ansys\solutions\my_solution\solution
    .
    ├── definition.py
    ├── my_step.py
    └── custom_optislang_manager.py


In this file, you need to implement 2 classes:
- A class that inherits from ``InternalOptislangManager`` and overrides the `PRODUCT_NAME` attribute to match the one that you set in the custom configuration class.
- A class that inherits from ``OptislangManager`` to point to the new internal manager.

.. code-block:: python

    from ansys.saf.product_manager.optislang import OptislangManager, InternalOptislangManager


    class InternalCustomOptislangManager(InternalOptislangManager):
        PRODUCT_NAME = "custom-optislang"


    class CustomOptislangManager(OptislangManager, instance_manager_impl_type=InternalCustomOptislangManager): ...


Use the new product instance manager in your solution
=====================================================

.. code-block:: none

    from pathlib import Path

    from ansys.saf.glow.solution import (
        StepModel,
        StepSpec,
        create_instance,
        instance,
        long_running,
        transaction,
    )

    from ansys.solutions.my_solution.solution.custom_optislang_manager import CustomOptislangManager


    class OptislangCustomStep(StepModel):

        @transaction(self=StepSpec())
        @create_instance("osl_manager", CustomOptislangManager)
        @long_running
        def launch_instance(self, osl_manager: CustomOptislangManager) -> None:
            osl_manager.initialize()

        @transaction(self=StepSpec())
        @instance("osl_manager")
        def use_instance(self, osl_manager: CustomOptislangManager) -> None:
            osl = osl_manager.instance
            project = osl.application.project
            # do something with project

        @transaction(self=StepSpec())
        @instance("osl_manager")
        def close_instance(self, osl_manager: CustomOptislangManager) -> None:
            osl_manager.shutdown()