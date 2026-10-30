.. _solution_configuration:

Solution configuration
######################

A solution configuration is an application-level data structure that allows the solution developer to store data in the database that is relevant
for the usage of a particular Solution. This data is defined by adding attributes to a subclass of the base class ``SolutionConfiguration``
(imported from ``ansys.saf.glow.solution``), which can be modified without changing the Solution. The solution configuration applies to all
projects of the Solution.


Default solution configuration
==============================

The base ``SolutionConfiguration`` class inherits from the Pydantic ``BaseModel`` and already includes two attributes:

.. code-block:: python

    glow_schema_version: int
    solution_schema_version: int

``glow_schema_version`` must not be modified by the solution developers.

``solution_schema_version`` indicates the current version of the solution configuration and allows the storage of an updated solution
configuration by increasing its value.


Extend the solution configuration
=================================

The solution configuration can be extended by inheriting from the base ``SolutionConfiguration`` class, allowing to add the required attributes
for the Solution usage. A custom ``SolutionConfiguration`` class must override the inherited ``solution_schema_version`` field, of type integer
and with a default value. In the following example, we incorporate an integer and a dictionary containing HPS server urls:

.. code-block:: python

    class ExtendedSolutionConfiguration(SolutionConfiguration):
        solution_schema_version: int = 1
        my_field: int = 1
        hps_server_urls: dict[str, HttpUrl] = {
            "my_hps_url": "http://localhost:8443",
            "another_hps_url": "http://another_host:8443",
        }

The solution configuration is stored in the database the first time there is an attempt to retrieve it while running the Solution.

Modifying the default value of an attribute of a solution configuration that has already been stored has no effect, as the stored attribute
value overwrites the default value. However, if a new attribute that is not present in the stored solution configuration is incorporated,
its default value in the solution configuration definition is used.

For example, if after storing the ``ExtendedSolutionConfiguration`` solution configuration above, the solution developer introduces the
following changes:

.. code-block:: python

    class ExtendedSolutionConfiguration(SolutionConfiguration):
        solution_schema_version: int = 1
        my_field: int = 2
        my_second_field: float = 5.0
        hps_server_urls: dict[str, HttpUrl] = {
            "my_hps_url": "http://localhost:8443",
            "another_hps_url": "http://another_host:8443",
        }

when using the solution configuration, the attribute ``my_field`` will have value ``1``, because this attribute was already stored, and
the attribute ``my_second_field`` will have the value ``5.0``, because it is a new attribute that is not yet stored in the database.


Use the solution configuration
==============================

To allow the usage of the solution configuration it must be added to a GLOW Solution definition as the ``solution_configuration`` attribute.

.. code-block:: python

    class ExtendedSolutionConfigurationSolution(Solution):
        display_name: str = "ExtendedSolutionConfiguration"
        steps: Steps
        solution_configuration: ExtendedSolutionConfiguration = ExtendedSolutionConfiguration()

There are three ways to have access to the solution configuration and its attributes: from the client, from within a transaction, or via a
request to the ``GET`` end point of the solution configuration API.

From the client
---------------

.. code-block:: python

    @callback(
        ...,
        State("url", "pathname"),
    )
    def run_hps_simple_job(n_clicks: int, project: ExtendedSolutionConfigurationSolution):
        """Callback function to trigger the computation."""
        hps_server_urls = project.solution_configuration.hps_server_urls
        ...

From within a transaction
-------------------------

.. code-block:: python

    @transaction(self=StepSpec())
    def my_transaction(self, extended_config: ExtendedSolutionConfiguration) -> None:
        hps_server_urls = extended_config.hps_server_urls
        ...

Via request to the solution configuration API
---------------------------------------------

.. code-block:: python

    response = httpx.get(f"{api_url}/solution-configuration")
    solution_configuration = ExtendedSolutionConfiguration.model_validate(response.json())


Modify the existing solution configuration schema
=================================================

If the definition of the solution configuration becomes incompatible with the stored solution configuration due to the introduction of a
breaking change, the solution developer must update the solution configuration version by incrementing the value of the
``solution_schema_version`` attribute. Then, by setting the environment variable :envvar:`GLOW_OVERWRITE_SOLUTION_CONFIG` and running the
Solution, the new solution configuration definition will be stored in the database completely replacing the old one. Breaking changes include
a modification of the type of an attribute and the removal of an attribute.

In the following example, we have modified the ``ExtendedSolutionConfiguration`` class by changing the type of its ``my_field`` attribute from
``int`` to ``str``. This constitutes a breaking change, so we also want to increment the value of the attribute ``solution_schema_version``.

.. code-block:: python

    class ExtendedSolutionConfiguration(SolutionConfiguration):
        solution_schema_version: int = 2
        my_field: str = "my_string"
        hps_server_urls: dict[str, HttpUrl] = {
            "my_hps_url": "http://localhost:8443",
            "another_hps_url": "http://another_host:8443",
        }


Modify the stored solution configuration
========================================

The solution configuration stored in the database can be completely or partially modified through the ``PUT`` end point of the solution
configuration API.

.. code-block:: python

    httpx.put(
        f"{api_url}/solution_configuration",
        json={
            "hps_server_urls": {
                "a_third_hps_url": "http://third_host:8443",
            },
        },
    ).raise_for_status()

.. warning::

    This should only be done by an administrator.

.. note::

    Currently, all users have the administrator role, but this will change in the future.


Example of a solution configuration
===================================

The following is an example of how to define a Solution that provides several HPS server urls, with which the user can run
HPS simple jobs, by means of an extended solution configuration that stores these HPS server urls.

.. code-block:: python

    class ExtendedSolutionConfiguration(SolutionConfiguration):
        solution_schema_version: int = 1
        hps_server_urls: dict[str, str] = {
            "my_hps_url": "http://localhost:5443",
            "another_hps_url": "http://another_host:5443",
        }


    class ExtendedSolutionConfigurationStep(StepModel):

        selected_hps_server_url: str | None = None

        @transaction(self=StepSpec(download=["selected_hps_server_url"]))
        def run_hps_simple_job(self) -> None:
            HpsSimpleProject.start_hps_job(
                input_values={"script": "my_script.py"},
                output_parameters={"output.txt": HpsOutputFileSpecification()},
                hps_server_url=self.selected_hps_server_url,
            )
            ...


    class Steps(StepsModel):
        extended_solution_configuration_step: ExtendedSolutionConfigurationStep


    class ExtendedSolutionConfigurationSolution(Solution):
        display_name: str = "ExtendedSolutionConfiguration"
        steps: Steps
        solution_configuration: ExtendedSolutionConfiguration = ExtendedSolutionConfiguration()

With this solution definition, a transaction that starts an HPS simple job can be invoked from the client as follows:

.. code-block:: python

    @callback(
        ...,
        State("url", "pathname"),
    )
    def run_hps_simple_job(n_clicks: int, selected_hps_server_alias: str, project: ExtendedSolutionConfigurationSolution):
        hps_server_urls = project.solution_configuration.hps_server_urls
        step = project.steps.extended_solution_configuration_step
        step.selected_hps_server_url = hps_server_urls[selected_hps_server_alias]

        step.run_hps_simple_job()
