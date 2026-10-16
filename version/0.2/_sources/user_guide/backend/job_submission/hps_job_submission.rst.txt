.. _hps_job_submission:

Submit jobs and parametric studies to HPS
#############################################

This section provides instructions for submitting jobs and parametric studies to HPS.
The GLOW APIs for submitting jobs and parametric studies are separate, but share many of the same features and elements.
The majority of the functionality is described in terms of submitting single jobs.
The API for submitting parametric studies is described in terms of the difference to the single job API.

Deployment contexts
===================
The HPS API is designed to operate across all the deployment types that SAF GLOW Engine  supports.
The API hides the details of connecting to the HPS service and managing HPS authentication.

Configuration
=============

.. _hps_configuration:

Install and start HPS
---------------------

HPS is a separate service that needs to be installed and started before it can be used.
Refer to the :ref:`HPS installation instructions <hps_installation>` for details on how to install and start HPS.

Install HPS extra dependencies
------------------------------

To use the HPS functionality, you need to install the ``core-hps`` extra from ``ansys-saf-sdk``.
This can be done by editing the ``ansys-saf-sdk`` dependency declaration in the ``pyproject.toml`` file of your solution as follows:

.. code-block:: toml

  [tool.poetry.dependencies]
    ansys-saf-sdk = {version = "^0.2.0", extras = ["core-hps"]}

The ``extras`` field specifies that you want to include the HPS-related dependencies.
Once you have updated the dependency, run the following command to install the extra dependencies:

.. tab-set::

  .. tab-item:: From within the solution virtual environment

      .. code-block:: bash

        poetry lock --no-update
        poetry install --all-extras --with=tests,doc,build

      .. code-block:: bash

        poetry install

  .. tab-item:: From within the SAF CLI virtual environment or terminal

      .. code-block:: bash

        saf execute <solution-name> "poetry lock --no-update"
        saf execute <solution-name> "poetry install --all-extras --with=tests,doc,build"

      .. code-block:: bash

        saf execute <solution-name> "poetry install"

Environment variables for HPS
-----------------------------

To enable access to HPS, the GLOW server needs to be configured with the environment variables listed in :ref:`this section <hps_jobs_configuration>` of the configuration documentation.

HPS authentication
==================

A solution derived from the SAF CLI template and deployed into the SAF platform builder environment will automatically
authenticate with HPS using the current user's identity. A solution derived from the SAF CLI template deployed as a windows application will trigger an
interactive login flow in the user's browser to authenticate with HPS the first time the solution executes the HPS API.

Read more about HPS authentication :ref:`here <hps_auth>`.


The GLOW HPS API and transaction methods
========================================

The HPS API is designed to be used in the context of a GLOW transaction method.
All the following examples are written in the context of a GLOW transaction method.

.. _hps_job_submit_single:

Submit a single job to HPS
==============================

From a transaction method a single job can be created and started in HPS as shown in the following example.

In the module ``ansys.solutions.ic_simulation.solution.hps_step`` the following method definition is used
to start a HPS job:

.. code-block:: python

    import time
    from ansys.saf.glow.solution.hps import HpsExecutionSpecification, HpsSimpleProject, NO_HPS_SIMPLE_PROJECT
    from ansys.solutions.ic_simulation.solution.scripts.simulate_ic import simulation


    class HpsStep(StepModel):
        ...

        hps_project: HpsSimpleProject = NO_HPS_SIMPLE_PROJECT
        result: float = 0.0

        @transaction(self=StepSpec(upload=["hps_project"]))
        def create_and_start_hps_job(self) -> None:

            execution_spec = HpsExecutionSpecification(
                function=simulation,
                output_parameters={"result_value": float},
                products=[Software("Ansys Electronics Desktop", version="2023 R1")],
                dependencies=["pyaedt==1.0.1"],
            )
            self.hps_project = execution_spec.execute(n=99)

        @transaction(self=StepSpec(download=["hps_project"], upload=["result"]))
        @long_running
        def wait_for_hps_job_completion(self) -> None:
            while not self.hps_project.finished:
                time.sleep(5)

            if self.hps_project.status.evaluation_status == HpsJobEvaluationStatus.EVALUATED:
                self.result = self.hps_project.result_value


In the module ``ansys.solutions.ic_simulation.solution.scripts.simulate_ic``
the code to be executed in HPS is defined as follows:

.. code-block:: python

    ...


    def simulation(n: int):
        # perform computation using aedt setting result to a float value
        ...
        return {"result_value": result}


In ``create_and_start_hps_job`` the call to ``HpsExecutionSpecification.execute`` captures the job inputs and creates a
job which is pending in the HPS system and available to be started by the HPS system (for more information on how to specify job inputs
see :ref:`this section <hps_job_inputs>`).

As shown in the above example the result of the call to ``HpsExecutionSpecification.execute`` can be assigned to a field of a step
enabling other methods to monitor the status of the HPS job and extract results from HPS
(see :ref:`this section on project handles <hps_job_persist_handle>` and
:ref:`this section on querying jobs for state and results <query_a_job>`).

The method ``wait_for_hps_job_completion`` waits for the HPS job to complete and, if the job is successful extracts the result of the job from HPS and
stores it in the project.

The ``output_parameters`` argument to ``HpsExecutionSpecification`` specifies the output parameters of the job (for more information on
how to specify job outputs see :ref:`this section <hps_job_outputs>`).
The function argument to ``HpsExecutionSpecification`` specifies the function to be executed in the job. This
function is expected to:

* have keyword arguments that match the arguments passed to ``HpsExecutionSpecification.execute``
* return a dictionary with entries for the outputs defined by the ``output_parameters`` argument to ``HpsExecutionSpecification``.

The inputs and outputs of the job are mapped by the transaction method code into step fields.
The name of a HPS job parameter does not correspond to a step field name.

For more information how to write a function compatible with ``HpsExecutionSpecification`` see :ref:`this section <hps_function>`.

The handling of transfers of files and directories to and from HPS is different from other input and output types.
The above linked sections provide more information on how to work with files and directories as inputs and outputs.

The ``products`` argument to ``HpsExecutionSpecification`` specifies the products that are required by the job
so that the job can assume that the given product is installed in the execution environment (for more information
see :ref:`this section <hps_job_specifying_required_products>`).
The ``dependencies`` argument to ``HpsExecutionSpecification`` specifies the Python packages that are required
by the job so that the job can assume that the given packages are installed in the Python environment in which
see :ref:`this section <hps_job_dependencies>`).

The ``HpsExecutionSpecification.execute`` method transfers a well defined set of source code to HPS for execution that
should include the function referenced by the ``function`` argument to ``HpsExecutionSpecification``
(see :ref:`this section <hps_default_source_code_transfer>` for more information).

A more detailed example of how to use the HPS job submission API can be found in
the `HPS example solution <https://dev-docs.external.solutions.ansys.com/version/stable/examples/saf_ex_hps_job_submission.html#hps-job-submission-and-events>`_.

Configure HPS job execution
---------------------------------

It is possible for alternative sets of source code to be transferred to HPS
(see :ref:`this section <hps_alternative_source_code_transfer>` for more information).

It is possible to specify specific versions of standard or Ansys Python to be used to run the job.
(see :ref:`this section <hps_specify_python_version>` and :ref:`this section <hps_run_with_ansys_python>` for more information).

(see :ref:`this section <hps_job_specify_resources>` for more information).

.. _hps_job_inputs:

Specify job inputs
------------------

The arguments to the ``execute`` method must be keyword arguments. These arguments define the HPS input parameters, files and directories for the job.
Input files are defined by arguments of the following types: ``EntityHandle``, ``Path``, ``HpsInputFileSpecification`` or ``HpsInputDirectorySpecification``.
All other arguments define input parameters to the HPS job.

The API will ensure that the filename of an input file, when copied to the current working directory during job execution, has the filename contained in the
supplied input objects (for example, the ``EntityHandle``).

Arguments that are ``HpsInputFileSpecification`` values can specify an entirely different path for the source of a file from the relative path where the file
will be copied in the current working directory during job execution.  (This allows an input file to be copied to a nested directory within the current working directory during job execution.)
The first argument to the ``HpsInputFileSpecification`` constructor is an ``EntityHandle`` or ``Path`` specifying the source of the file and
the second argument is a string specifying a relative path where the file will be stored in the current working directory during job execution.

Arguments that are ``HpsInputDirectorySpecification`` values can specify an entirely different path for the source of a directory from the relative path where the directory
will be copied in the current working directory during job execution. (This allows an input directory to be copied to a nested directory within the current working directory during job execution.)
The first argument to the ``HpsInputDirectorySpecification`` constructor is an ``EntityHandle`` or ``Path`` specifying the source of the directory and the second argument is a string specifying a relative path where the
directory will be stored in the current working directory during job execution.

``HpsInputFileSpecification`` and ``HpsInputDirectorySpecification`` should be imported from the ``ansys.saf.glow.solution.hps`` module.

A detailed example of how to use the HPS job submission API to submit inputs directly and via files can be found in
the `HPS example solution (Start Job Section) <https://dev-docs.external.solutions.ansys.com/version/stable/examples/saf_ex_hps_job_submission.html#backend-solution-definition-start-job>`_.

.. _hps_job_outputs:

Specify job outputs
-----------------------

The ``output_parameters`` argument to ``HpsExecutionSpecification`` is a dictionary which defines the HPS output parameters, files and directories for the job.
Output parameters are defined by entries with type values. Output files are defined by entries with ``HpsOutputFileSpecification`` values.
Output directories are defined by entries with ``HpsOutputDirectorySpecification`` values.

The ``HpsOutputFileSpecification`` constructor has an optional string first argument which is the relative path of the output file in the current working directory during job execution.
If this argument is not supplied, the output file name is the same as the dictionary key of the output file.

.. note::
    When setting an ``HpsOutputFileSpecification`` output parameter, if the file in the HPS job context has an extension, but the ``evaluation_path`` of the file is not specified
    in ``HpsOutputFileSpecification``, HPS will try to find a file which name corresponds to the key of the output parameter without the extension.

The ``HpsOutputDirectorySpecification`` constructor has an optional string first argument which is the relative path of the output directory in the current working directory during job execution.
If this argument is not supplied, the output directory name is the same as the dictionary key of the output directory.

A detailed example of how to use the HPS job submission API to extract outputs directly and via files can be found in
the `HPS example solution (declare job section) <https://dev-docs.external.solutions.ansys.com/version/stable/examples/saf_ex_hps_job_submission.html#backend-solution-definition-declare-job>`_.

.. _hps_function:

Functions executed in HPS
-------------------------

The ``function`` argument to ``HpsExecutionSpecification`` refers to a Python function to be executed in the HPS job.
This function must be defined in the source code transferred to HPS for execution which by default is the content of the ``scripts`` directory located
in the directory containing the step definition module that contains the transaction method that calls ``execute``
(see :ref:`this section <hps_default_source_code_transfer>` for more information).  The default source code transfer can be overridden
(see :ref:`this section <hps_alternative_source_code_transfer>` for more information).

The ``function`` argument can be a Python function object.
This function must not be a method of a class, a lambda function or nested within another function.

Alternatively the ``function`` argument can be a string of the form ``<module name>.<function-name>``.
For example the string ``ansys.solutions.solution_with_hps_python_script.scripts.simple_use_sympy.compute_series``
refers to a function called ``compute_series`` in the module ``ansys.solutions.solution_with_hps_python_script.scripts.simple_use_sympy``.

The function should have a set of keyword arguments that match the arguments passed to ``execute``.
The ``execute`` arguments referring to files and directories
(``EntityHandle``, ``Path``, ``HpsInputFileSpecification`` or ``HpsInputDirectorySpecification``)
will be passed to the function as ``Path`` objects.
Otherwise the arguments will be passed to the function unchanged.

The function should return a dictionary with entries for all the outputs, defined by the ``output_parameters``
argument to ``HpsExecutionSpecification``, which are not files or directories. The values of the dictionary
should have types corresponding to those defined in the ``output_parameters`` argument.

The function should simply write the output files and directories to the paths specified in the ``output_parameters``
relative to the current working directory.

A detailed example of how to code a function for execution on HPS that supports the transfer of data directly and via files can be found in
the `HPS example solution (Job run in HPS section) <https://dev-docs.external.solutions.ansys.com/version/stable/examples/saf_ex_hps_job_submission.html#backend-function-that-is-executed-in-hps>`_.

The function can have an optional ``context`` argument of type ``HpsExecutionContext``.
If this argument is present it will provide information about the execution environment and the job to the function.

The ``context`` object has the has following properties:

* ``products`` - a list of ``HpsProduct`` objects that contain information about the Ansys products that were requested for this job plus the Python version, Ansys Python version, or SAF Product Environment in which the job is running
* ``required_output_files`` - dictionary mapping to output key names to the specified output file paths for those files
* ``required_output_directories`` - dictionary mapping to output key names to the specified output directory paths for those directories
* ``required_output_parameters`` - a list of output parameter key names
* ``input_parameters`` - a dictionary mapping input parameter key names to their values (corresponds exactly to the arguments passed to the function apart from the ``context`` object).

The ``HpsProduct`` objects have the following properties:

* ``name`` - the HPS product name
* ``version`` - the HPS product version
* ``executable`` - the executable path for the product



.. _hps_default_source_code_transfer:

Source code transfer
--------------------

By default the source code transferred to HPS for execution is the content of the ``scripts`` directory located
in the directory containing the step definition module that contains the transaction method that calls ``execute``.

For example consider the following directory structure:

.. code-block:: text

    my_solution/
    ├── pyproject.toml
    ├── README.md
    ├── src
    │   └── ansys
    │       └── solutions
    │           └── solution_with_hps_python_script
    │               └── solution
    │                   ├── hps_parametric_study.py
    │                   └── scripts
    │                       ├── simple_use_sympy.py
    │                       └── other_module.py

where

* ``hps_parametric_study.py`` contains the transaction method that calls ``execute`` and
* ``simple_use_sympy.py`` contains the function ``compute_series`` to be executed in HPS.
* ``other_module`` is imported into ``simple_use_sympy.py`` via the statement ``import ansys.solutions.solution_with_hps_python_script.scripts.other_module``.

The above source code can be referenced by ``HpsExecutionSpecification`` as follows:

.. code-block:: python

    from ansys.solutions.solution_with_hps_python_script.solution.scripts.simple_use_sympy import compute_series

    HpsExecutionSpecification(function=compute_series, output_parameters={"result": str})

or the following, if ``simple_use_sympy`` cannot be imported into the solution definition
because the solution doesn't contain the required dependencies:

.. code-block:: python

    HpsExecutionSpecification(
        function="ansys.solutions.solution_with_hps_python_script.solution.scripts.simple_use_sympy.compute_series",
        output_parameters={"result": str},
    )

The idea behind this scheme is to ensure that the IDE containing the solution definition can resolve the imports used in the
code transferred to HPS.

The code contained in the scripts directory must only import modules that are:

* part of standard python packages;
* part of packages referenced by the ``dependencies`` argument to ``HpsExecutionSpecification``; or
* contained within the scripts directory.

.. _hps_alternative_source_code_transfer:

Alternative source code transfer
--------------------------------

It is possible to override the transfer of the ``scripts`` directory by passing
a value for the optional ``module`` argument to ``HpsExecutionSpecification``.
This might be useful if the ``scripts`` directory is large and contains code that is not needed for the specific HPS job.
The ``module`` argument is either a Python module object or a string containing the module name.

For example consider the following directory structure:

.. code-block:: text

    my_solution/
    ├── pyproject.toml
    ├── README.md
    ├── src
    │   └── ansys
    │       └── solutions
    │           └── solution_with_hps_python_script
    │               └── solution
    │                   ├── hps_parametric_study.py
    │                   └── alternative
    │                       ├── simple_use_sympy.py
    │                       └── other_module.py

where

* ``hps_parametric_study.py`` contains the transaction method that calls ``execute`` and
* ``simple_use_sympy.py`` contains the function ``compute_series`` to be executed in HPS.
* ``other_module`` is imported into ``simple_use_sympy.py`` via the statement ``import ansys.solutions.solution_with_hps_python_script.solution.alternative.other_module``.

The above source code can be referenced by ``HpsExecutionSpecification`` as follows:

.. code-block:: python

    from ansys.solutions.solution_with_hps_python_script.solution.alternative.simple_use_sympy import compute_series
    from ansys.solutions.solution_with_hps_python_script.solution import alternative

    HpsExecutionSpecification(function=compute_series, module=alternative, output_parameters={"result": str})

or the following, if ``simple_use_sympy`` cannot be imported into the solution definition
because the solution doesn't contain the required dependencies:

.. code-block:: python

    HpsExecutionSpecification(
        function="ansys.solutions.solution_with_hps_python_script.solution.alternative.simple_use_sympy.compute_series",
        module="ansys.solutions.solution_with_hps_python_script.solution.alternative",
        output_parameters={"result": str},
    )

The idea behind this scheme is to ensure that the IDE containing the solution definition can resolve the imports used in the
code transferred to HPS.

The code contained in the alternative module directory must only import modules that are:

* part of standard python packages
* part of packages referenced by the ``dependencies`` argument to ``HpsExecutionSpecification``
* contained within the module directory.

.. _hps_job_specifying_required_products:

Specify required products
-----------------------------

The ``products`` argument to ``HpsExecutionSpecification`` is a list which specifies the products that are required by the job.
The job cannot expect a product to be installed in the HPS execution environment where the job is running unless it is specified in this list.
The job will not have access to information about an installed product such as the location of the product executable unless
the product is specified in this list.

The content of the ``products`` list has no effect on the PyAnsys libraries that are available to the job.
The PyAnsys libraries that are available to the job are determined by other arguments to ``HpsExecutionSpecification``.

Each entry in the ``products`` list is a ``Software`` object.
The first argument to the ``Software`` object constructor is the HPS name of the product.

The second optional argument of the ``Software`` object constructor is the version of the product required and follows the pattern ``<year> R<release>`` for Ansys products.

``Software`` should be imported from ``ansys.saf.product_configuration.interfaces``.

A job will run only if all the specified product versions are available together in an execution environment in the HPS service.

.. _hps_job_dependencies:

Package dependencies
----------------------

It is possible to run the HPS job in a Python virtual environment with a specific set of installed packages
by passing a list of package dependencies to ``HpsExecutionSpecification`` in the ``dependencies`` argument. Each entry in the list is a string containing
`a pip requirement specifier <https://pip.pypa.io/en/stable/reference/requirement-specifiers/#requirement-specifiers>`_.

Specifying dependencies will ensure that the job is run in a virtual environment that contains the specified packages.
The job will be configured in HPS such that SAF Product Environment is not a required product of the job.

If SAF Product Environment is installed in HPS then the uv package is used to create and cache the virtual environment
so that the overhead of using the virtual environment is minimised.

If SAF Product Environment is not installed in HPS then a virtual environment is created for each job which creates an execution time overhead for the job.

The default configuration of this functionality requires public internet access from the HPS execution environment.

.. _hps_specify_python_version:

Specify Python version
-----------------------

The required Python version is specified by the optional ``python_version`` string argument to ``HpsExecutionSpecification`` of the form ``<major>.<minor>`` for example "3.11".
By default the latest version of Python available in HPS is used.

.. _hps_run_with_ansys_python:

Run with Ansys Python
---------------------

It is possible to run the job using Ansys Python instead of "pure" Python by setting the optional ``use_ansys_python`` boolean argument to ``True``

The required Python version is specified by the optional ``python_version`` string argument to ``HpsExecutionSpecification`` with the form ``<ansys version> Python 3.11`` (for example, "2025 R2 Python 3.11").

.. _hps_job_specify_resources:

Specify resource requirements
--------------------------------

It is possible to specify the resource requirements for the HPS execution job by passing a ``ResourceRequirements`` object to ``HpsExecutionSpecification`` in the optional ``resource_requirements`` argument.

The following example shows how to set the resource requirements:

.. code-block:: python

    @transaction(
        self=StepSpec(
            upload=["hps_project"],
            download=["first_arg", "second_arg", "sel_queue_name"],
        )
    )
    def start_parametric_study_using_queue_name(self) -> None:
        resource_requirements = ResourceRequirements(
            platform="linux", num_cores=1, memory=32768e3, hpc_resources=HpcResources(queue=self.sel_queue_name)
        )
        spec = HpsExecutionSpecification(
            function=add,
            output_parameters={"result": HpsOutputFileSpecification(evaluation_path="output.txt")},
            resource_requirements=resource_requirements,
        )
        self.hps_project = spec.execute(x=self.first_arg, y=self.second_arg)

.. _hps_job_software_resource_analysis:

Automatic analysis of the software and resource requirements
------------------------------------------------------------

Before submitting a job to HPS, the GLOW HPS API will compare the requested :ref:`software <hps_job_specifying_required_products>` and :ref:`resource <hps_job_specify_resources>` requirements with those available in the HPS execution environment and return an ``HpsJobValidationError`` if the requirements cannot be met.

.. _hps_job_persist_handle:

Persist a handle to a Job
--------------------------

The result of the call to ``execute`` can be stored in a project by assignment to a GLOW step field. For example:

.. code-block:: python

    from ansys.solutions.ic_simulation.scripts.simulate_ic import simulation


    class JobStep(StepModel):
        """simple HPS job which uses parameters to get data in and out of the job"""

        first_arg: float = 0.0
        second_arg: float = 0.0
        add_script: EntityHandle = NO_ENTITY

        hps_project: HpsSimpleProject = NO_HPS_SIMPLE_PROJECT

        @transaction(self=StepSpec(upload=["hps_project"], download=["first_arg", "second_arg", "add_script"]))
        def start_job(self):

            execution_spec = HpsExecutionSpecification(
                function=simulation,
                output_parameters={"result": int},
                products=[Software("Ansys Electronics Desktop", version="2023 R1")],
                dependencies=["pyaedt==1.0.1"],
            )
            hps_project = execution_spec.execute(n=99)

The value ``NO_HPS_SIMPLE_PROJECT`` is an empty placeholder and can be imported from the ``ansys.saf.glow.solution.hps`` module.

A persisted job handle can be used to query the state of the job, transfer files to and from the job, and access the results of the job
in transaction methods following the transaction method that submitted the job.

.. _query_a_job:

Query and retrieve data from a job
=======================================

.. _querying_the_state_of_a_job:

Query the state of a Job
---------------------------

A ``HpsSimpleProject`` object has the following properties that can be used to query the state of the job:

* ``exists`` This property is a boolean that is ``True`` if the job exists in the HPS system and ``False`` otherwise.
* ``ui_url`` This property returns the HPS UI URL for the project containing the job.
* ``finished`` This property is a boolean that is ``True`` if the job is no longer pending or running and ``False`` otherwise.
* ``status`` This property returns a value of type ``IHpsJobStatus`` which has a property ``evaluation_status`` which returns a ``HpsJobEvaluationStatus`` value.

``HpsJobEvaluationStatus`` is an enumeration with the following members:

* ``PENDING``
* ``PROLOG``
* ``RUNNING``
* ``EVALUATED``
* ``FAILED``
* ``ABORTED``
* ``TIMEOUT``


Only the ``EVALUATED`` status indicates that the job has completed successfully.

``HpsJobEvaluationStatus`` can be imported from the ``ansys.saf.glow.solution.hps`` module.

Access the parameters and files of a job
-----------------------------------------
The parameters and files associated with a job can be accessed via attributes of the ``HpsSimpleProject`` object.
For example, if a job has a float parameter ``result``, then the ``HpsSimpleProject`` referring to the job will have
the attribute ``result`` which returns the float value once the job is in the evaluated state.
The same pattern applies to files and directories, except that the result of the attribute is an ``EntityHandle`` object which is a handle to an HPS file or directory.
For a description of how HPS files and directories can be transferred to the transaction method file space, see :ref:`on transferring files from HPS <hps_job_transferring_files>`.

Query example
-------------

The following is an example of a transaction method that queries and retrieves data from a HPS job
where ``result`` has been specified as a float output parameter.

.. code-block:: python

    @transaction(self=StepSpec(upload=["calculate_result"], download=["hps_project"]))
    def query_hps(self):
        """Query the parameter study and update results."""
        if self.hps_project.exists:
            status = self.hps_project.status
            if status.evaluation_status == HpsJobEvaluationStatus.EVALUATED:
                result = str(self.hps_project.result)
            elif status.evaluation_status == HpsJobEvaluationStatus.FAILED:
                result = "ERROR"
            elif status.evaluation_status == HpsJobEvaluationStatus.ABORTED:
                result = "ABORTED"
            elif status.evaluation_status == HpsJobEvaluationStatus.TIMEOUT:
                result = "TIMEOUT"
            else:
                result = None
        else:
            result = None

        self.calculate_result = result

.. _hps_job_transferring_files:

Transfer files and directories from HPS
---------------------------------------

Within a transaction method, a handle on an HPS file or directory retrieved from a ``HpsSimpleProject`` allow access to the data in the file or directory.
(The ``EntityHandle`` is obtained from property of a ``HpsSimpleProject`` where the property has the name corresponding to the key of an output file or directory.)

The file or directory can be uploaded into a GLOW project either:

.. tab-set::

    .. tab-item:: EntityHandle

        By retrieving the file contents with the transaction's storage scope.

        .. code-block:: python

            class JobStep(StepModel):

                glow_result: str = ""
                first_arg: float = 0.0
                second_arg: float = 0.0

                result_from_output_dir: str = ""

                hps_project: HpsSimpleProject = NO_HPS_SIMPLE_PROJECT

                @transaction(self=StepSpec(upload=["hps_project"], download=["first_arg", "second_arg"]))
                def start_job(self):
                    """Compute the sum of two numbers."""
                    spec = HpsExecutionSpecification(
                        function=add,
                        output_parameters={
                            "job_result": HpsOutputFileSpecification(
                                evaluation_path="result.txt",
                                collect_interval=3,
                                return_type=EntityHandle,
                            ),
                            "job_output_files_dir": HpsOutputDirectorySpecification(
                                evaluation_path="output_files",
                            ),
                        },
                    )
                    self.hps_project = spec.execute(x=self.first_arg, y=self.second_arg)

                @transaction(self=StepSpec(upload=["glow_result"], download=["hps_project"]))
                def fetch_file(self):
                    self.glow_result = self.storage_scope.get_text(self.hps_project.job_result)

                @transaction(self=StepSpec(upload=["result_from_output_dir"], download=["hps_project"]))
                def fetch_directory(self):
                    file_content_from_output_dir = (
                        self.storage_scope.get_cached(self.hps_project.job_output_files_dir) / "some_file.txt"
                    )
                    self.result_from_output_dir = file_content_from_output_dir.read_text()

        ``job_result`` is a key name passed in the ``output_parameters`` dictionary where the value is a ``HpsOutputFileSpecification``.
        ``job_output_files_dir`` is a key name passed in the ``output_parameters`` dictionary where the value is a ``HpsOutputDirectorySpecification``.


.. _hps_job_transferring_files_during_evaluation:

Transfer files and directories from HPS during evaluation
---------------------------------------------------------

HPS enables file and directory download during evaluation. This is enabled when the ``collect_interval`` parameter of the ``HpsOutputFileSpecification`` / ``HpsOutputDirectorySpecification`` is set to a value greater than 0.
In the following example, the file ``result.txt`` is collected every 3 seconds during the evaluation of the job. If the file is not yet available on HPS side, this query ``result_file = self.hps_project.result``
returns ``None``. Otherwise, it returns a ``EntityHandle`` object that can be used to read the file content. The same applies to directories.

.. tab-set::

    .. tab-item:: EntityHandle

        .. code-block:: python

            class FileJobStep(StepModel):

                result: EntityHandle = NO_ENTITY

                hps_project: HpsSimpleProject = NO_HPS_SIMPLE_PROJECT

                @transaction(self=StepSpec(upload=["hps_project"]))
                def start_job(self) -> None:
                    spec = HpsExecutionSpecification(
                        function=add,
                        output_parameters={
                            "result": HpsOutputFileSpecification(
                                evaluation_path="result.txt",
                                collect_interval=3,
                                return_type=EntityHandle,
                            )
                        },
                        products=[GlowSoftware("Ansys optiSLang", version="2024 R1")],
                        resource_requirements=ResourceRequirements(num_cores=7),
                        use_product_environment=False,
                        python_version="3.11",
                        dependencies=["ansys-optislang-core==0.7.1"],
                    )

                    self.hps_project = spec.execute()

                    while True:

                        # Try to fetch result.txt
                        result_handle = self.hps_project.result
                        if result_handle != NO_ENTITY:
                            result = self.storage_scope.get_text(result_handle)

                        status = self.hps_project.status
                        if status.evaluation_status in [
                            HpsJobEvaluationStatus.FAILED,
                            HpsJobEvaluationStatus.ABORTED,
                            HpsJobEvaluationStatus.TIMEOUT,
                        ]:
                            raise Exception(f"HPS job failed with status {status.evaluation_status}")
                        elif status.evaluation_status == HpsJobEvaluationStatus.EVALUATED:
                            break

                        time.sleep(2)


Query HPS resources
======================

Through the GLOW HPS API, it is possible to check the resources to run jobs that are available to HPS through the classes ``HpsSimpleProject`` and ``HpsParametricStudyProject``. These two classes offer a static method ``get_compute_resource_sets`` that returns a list of ``HpsComputeResourceSet`` objects.
Each of these objects has a ``name`` attribute and contains a list of ``HpsQueue`` objects that represent an available resource to execute and HPS job.

The following code shows how to retrieve this information inside a transaction and then use it to launch an HPS job in a different transaction:

.. code-block:: python

    @transaction(self=StepSpec(upload=["compute_resources"]))
    def get_compute_resource_sets(self) -> None:
        self.compute_resources = HpsParametricStudyProject.get_compute_resource_sets()

.. code-block:: python

    # Example of the output of HpsParametricStudyProject.get_compute_resource_sets()
    [HpsComputeResourceSet(name="local", queues=[HpsQueue(name="username-Virtual-Machine")])]


.. _hps_parametric_study:


The HPS Parametric Study API
============================

Using the GLOW HPS API, it is possible to create a parametric study in HPS in which a job script and input files are applied to a
set of design points over the input parameter space.  (A design point being a set of values for the parameters.)
The API enables a set of design points to be submitted with a script and input files. The script and input files apply to all design points.


Differences between the job API and the parametric API
------------------------------------------------------

The API for submitting and managing parametric studies is similar to the API for jobs but with the following differences:

* The handle for a parametric study is a ``HpsParametricStudyProject`` object which is returned by the ``HpsExecutionSpecification.execute_parametric_study`` method.
* The arguments to ``execute_parametric_study`` are identical to the arguments to ``execute`` except that values that are not ``Path``, ``HpsInputFileSpecification``, ``HpsInputDirectorySpecification`` or ``EntityHandle`` object are expected to be lists of values. These lists define a set of design points. The file and directory arguments are common to all design points.

* The attributes of an ``HpsParametricStudyProject`` object corresponding to parameters, files and directories are lists of values (as opposed to just values).
* The ``status`` property of the ``HpsParametricStudyProject`` object is replaced by the ``get_status_of_design_points`` method
* ``HpsParametricStudyProject`` has the following additional methods:

  * ``fetch_values_of_parameter``
  * ``fetch_values_of_parameters``
  * ``fetch_files``
* Various methods of the ``HpsParametricStudyProject`` object accept ``HpsDesignPointSelection`` objects as arguments to filter their results.
* The placeholder value of ``HpsParametricStudyProject`` is ``NO_HPS_STUDY_PROJECT``.

.. _submit_parametric_study:

*Example of submitting a parametric study*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following is an example of submitting a parametric study:

.. code-block:: python

    spec = HpsExecutionSpecification(
        function=simulate,
        output_parameters={"result": float, "result_file": HpsOutputFileSpecification()},
        products=[Software("Ansys Electronics Desktop", version="2023 R1")],
        dependencies=["pyaedt==1.0.1"],
    )

    hps_project = spec.execute_parametric_study(
        aedt_project=project, S=[1.0, 2.0, 3.0], W=[0.1, 0.2, 0.3], aedt_design_name=["waveguide", "waveguide", "waveguide"]
    )


The names of the arguments to ``execute_parametric_study`` are the names of the input parameters.
The values of those arguments are lists of values for the input parameters.
The list items at that a given index across all the lists in the arguments define a single design point.
In this example there are three design points with the values of the input parameters being
``(1.0, 0.1, "waveguide")``, ``(2.0, 0.2, "waveguide")`` and ``(3.0, 0.3, "waveguide")``.

Monitor the progress of a parametric study in HPS
-------------------------------------------------

A parameter study submitted via the GLOW HPS API consists of a single HPS project containing a job for each design point.
Each job has an independent execution state.

The progress of a parametric study can be monitored by calling the ``get_status_of_design_points`` method of the ``HpsParametricStudyProject`` object.
This method returns a list of ``IHpsJobStatus`` objects where each object corresponds to a design point.
The order of the objects in the list corresponds to the order of the design points passed to ``execute_parametric_study``.

The ``IHpsJobStatus`` object has a property ``evaluation_status`` which returns a ``HpsJobEvaluationStatus`` value.
``HpsJobEvaluationStatus`` is described in more detail in the section :ref:`on querying the state of a job <querying_the_state_of_a_job>`.

.. _accessing_parametric_study_results:

Access the results of a parametric study in HPS
-----------------------------------------------

The values of parameters, files and directories for each design point in a parametric study can be accessed via attributes of the ``HpsParametricStudyProject`` object.
For example, if the submitted study has a float parameter ``result``, then the ``HpsParametricStudyProject`` referring to the study will have
the attribute ``result`` which returns a list of float values. The order of the list corresponds to the order of the design points passed to
``execute_parametric_study``.  If the job corresponding to the design point is not in the ``EVALUATED`` state, then the value will be ``None``.

The content of the list of values for an output file is a list of ``EntityHandle`` objects which are handles to HPS files.
The content of the list of values for an output directory is a list of ``EntityHandle`` objects which are handles to HPS directories.
The content of the list of values for an output parameter is a list of values of the type specified in the ``output_parameters`` dictionary
passed to ``HpsExecutionSpecification``.

This pattern is conceptually simple; however, it does not scale well to large numbers of design points.
The HPS API provides methods to fetch the values of parameters and files for subsets of design points.
The sections after the following example describe these methods.

Example of accessing the status and result of a parametric study
----------------------------------------------------------------

.. code-block:: python

    class ParametricStep(StepModel):

        calculate_result: list[str | None] = []
        number_left: int = 0
        hps_project: HpsParametricStudyProject = NO_HPS_STUDY_PROJECT

        @transaction(self=StepSpec(upload=["calculate_result", "number_left"], download=["hps_project"]))
        def query_parametric_study(self):
            """Query the parameter study and update results."""
            self.calculate_result = []
            number_left = 0
            for index, status in enumerate(self.hps_project.get_status_of_design_points()):
                if status.evaluation_status == HpsJobEvaluationStatus.EVALUATED:
                    result = str(self.hps_project.result[index])
                elif status.evaluation_status == HpsJobEvaluationStatus.FAILED:
                    result = "ERROR"
                elif status.evaluation_status == HpsJobEvaluationStatus.ABORTED:
                    result = "ABORTED"
                elif status.evaluation_status == HpsJobEvaluationStatus.TIMEOUT:
                    result = "TIMEOUT"
                else:
                    result = None
                    number_left += 1
                self.calculate_result.append(result)

            self.number_left = number_left

Access sets of output files in HPS
----------------------------------

.. tab-set::

    .. tab-item:: EntityHandle (files)

        By defining a file output parameter using ``HpsOutputFileSpecification``, when accessing the parameter as an attribute of the ``hps_project`` object, it already returns a list of ``EntityHandle`` objects, one for every design point.

        .. code-block:: python

            class ParametricStep(StepModel):
                result_files: list[EntityHandle] = []
                hps_project: HpsParametricStudyProject = NO_HPS_STUDY_PROJECT

                @transaction(self=StepSpec(upload=["hps_project"]))
                def launch_study(self):
                    spec = HpsExecutionSpecification(
                        function=simulate,
                        output_parameters={"result": float, "result_file": HpsOutputFileSpecification(return_type=EntityHandle)},
                        products=[Software("Ansys Electronics Desktop", version="2023 R1")],
                        dependencies=["pyaedt==1.0.1"],
                    )
                    self.hps_project = spec.execute_parametric_study(
                        aedt_project=project,
                        S=[1.0, 2.0, 3.0],
                        W=[0.1, 0.2, 0.3],
                        aedt_design_name=["waveguide", "waveguide", "waveguide"],
                    )

                @transaction(self=StepSpec(upload=["result_files"], download=["hps_project"]))
                def upload_to_project(self):
                    self.result_files = self.hps_project.result_file  # type: ignore

    .. tab-item:: EntityHandle (directories)

        By defining a file output parameter using ``HpsOutputDirectorySpecification``, when accessing the parameter as an attribute of the ``hps_project`` object, it already returns a list of ``EntityHandle`` objects, one for every design point.

        .. code-block:: python

            class ParametricStep(StepModel):
                result_directories: list[EntityHandle] = []
                hps_project: HpsParametricStudyProject = NO_HPS_STUDY_PROJECT

                @transaction(self=StepSpec(upload=["hps_project"]))
                def launch_study(self):
                    spec = HpsExecutionSpecification(
                        function=simulate,
                        output_parameters={"result": float, "result_directory": HpsOutputDirectorySpecification()},
                        products=[Software("Ansys Electronics Desktop", version="2023 R1")],
                        dependencies=["pyaedt==1.0.1"],
                    )
                    self.hps_project = spec.execute_parametric_study(
                        aedt_project=project,
                        S=[1.0, 2.0, 3.0],
                        W=[0.1, 0.2, 0.3],
                        aedt_design_name=["waveguide", "waveguide", "waveguide"],
                    )

                @transaction(self=StepSpec(upload=["result_directories"], download=["hps_project"]))
                def upload_to_project(self):
                    self.result_directories = self.hps_project.result_directory  # type: ignore



Alternative means of accessing the results of a parametric study
----------------------------------------------------------------

As an alternative to accessing attributes of ``HpsParametricStudyProject`` object to obtain the values of parameters or
handles on files (see :ref:`a previous section <accessing_parametric_study_results>` for details of this simple approach),
the ``fetch_values_of_parameter`` method of the ``HpsParametricStudyProject`` object allows
the value of a parameter, file or directory handle to be retrieved across design points.
The argument to ``fetch_values_of_parameter`` is the keyword of the output parameter, file or directory entry passed to
``execute_parametric_study``.
The result is a list of values where each value corresponds to a design point and is either

* a value of the type specified in the ``output_parameters`` dictionary;
* an ``EntityHandle`` object; or
* ``None``, if the job corresponding to the design point is not in the ``EVALUATED`` state.

The above method has performance limitations when there are a number of parameters to be fetched.
The ``fetch_values_of_parameters`` method of the ``HpsParametricStudyProject`` object allows the values of multiple
parameters or files to be fetched in a single call.
The argument is a list of keywords of the output parameter, file or directory entries passed to ``execute_parametric_study``.
The result is a list of lists of values. The outer list corresponds to the keys and
the inner list is a list of parameter values, file or directory handles, or ``None`` values where the design pint has not been
evaluated.

Filter the set of design points when fetching data
-----------------------------------------------------

In practice, a design point study may involve a very large number of design points with only a
very small number of design points being relevant to a given transaction method. For performance and convenience, the HPS
API provides a mechanism to filter the set of design points when fetching design point data.

The API provides the ``HpsDesignPointSelection`` class which defines a subset of design points.
Values of ``HpsDesignPointSelection`` can be passed as additional optional arguments to the ``get_status_of_design_points``,
``fetch_values_of_parameter`` and ``fetch_values_of_parameters`` methods of the ``HpsParametricStudyProject`` object to
restrict the data returned by those functions.

The ``HpsDesignPointSelection`` constructor has the following optional arguments:

* ``required_design_points`` - a list of integers specifying the indices of the design points to be included in the selection.
* ``eval_status`` - a ``HpsJobEvaluationStatus`` value or list of ``HpsJobEvaluationStatus`` values specifying the evaluation status of the design points to be included in the selection.
* ``limit`` - an integer specifying the maximum number of design points to be included in the selection.
* ``offset`` - an integer specifying the number of design points to skip before including design points in the selection.
* ``sort`` - a string or list of strings specifying the keys of the parameters to sort the design points by.
* ``parameter_filter`` - a dictionary specifying a filter based on parameter values.

The ``required_design_points``, ``eval_status`` and ``parameter_filter`` arguments, when present, combine to
define a base set of design points. This base set can then be sorted via the ``sort`` argument.
The base set is then further restricted by the ``limit`` and ``offset`` arguments.

The ``parameter_filter`` argument is a dictionary.
The values of the dictionary are either parameter values or lists of parameter values. The keys are either the
name of a parameter or a string of the form ``<parameter_name>.<operator>``.
Only parameters which have a type ``int``, ``float``, ``str`` or ``bool`` can be used in the filter.
Valid operators are:

* ``=`` - equal to
* ``ne`` - not equal to
* ``lt`` - less than
* ``le`` - less than or equal to
* ``gt`` - greater than
* ``ge`` - greater than or equal to
* ``in`` - in a list of values
* ``contains`` - contains value (which is expected to be a string) as part of the parameter value (which expected to be a string)

If the name of the parameter is used alone in the key, then the relationship is "equal to" if the value is not a list and "in" if the value is a list.
The entries in the dictionary are combined to form a filter over the design points. A design point must meet the criteria of all dictionary entries to be included.

.. note::

    As of July 2024, the ``sort``, ``required_design_point`` and ``parameter_filter`` functionality, although supported by the underlying PyHPS API, has significant defects in the HPS implementation.

Relate filtered design points to the input design point set
-----------------------------------------------------------

The ``fetch_values_of_parameters`` method supports an implicit parameter ``index`` which is the index of the design point
in the set of design points passed to the ``execute_parametric_study`` call. By specifying the ``index`` parameter in the list of keys passed to
``fetch_values_of_parameters``, the method will include a list of index values in the result.
This allows the result to be related back to the input design points even if the data has been filtered and sorted using a ``HpsDesignPointSelection`` object.

Examples of fetching design point data
---------------------------------------

The following examples of fetching design point data are based on the study created by the following calls:

.. code-block:: python

    spec = HpsExecutionSpecification(function=add, output_parameters={"result": float})
    hps_project = spec.execute_parametric_study(x=[4.0, 3.0, 5.0, 6.0, 7.0, 8.0], y=[6.0, 5.0, 7.0, 8.0, 9.0, 10.0])

The script simply computes the sum of two input parameters.

*Fetch all the evaluated design points*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    x = hps_project.fetch_values_of_parameters(
        ["result", "index"], HpsDesignPointSelection(eval_status=HpsJobEvaluationStatus.EVALUATED)
    )

``x`` will be a dictionary with keys ``"result"`` and ``"index"``.
The value of ``"result"`` will be a list of computed sums and the value of ``"index"`` will be a
corresponding list of indexes into the list of input design points.

*Fetch the computed sums for design points where the sum is greater than 10*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    x = hps_project.fetch_values_of_parameters(
        ["result", "index"],
        HpsDesignPointSelection(parameter_filter={"result.ge": 10.0}, eval_status=HpsJobEvaluationStatus.EVALUATED),
    )

*Fetch the top 2 computed sums*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    x = hps_project.fetch_values_of_parameters(
        ["result", "index"], HpsDesignPointSelection(sort="result", limit=2, eval_status=HpsJobEvaluationStatus.EVALUATED)
    )

*Fetch the computed sums for design points based on specific input values*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    x = hps_project.fetch_values_of_parameters(
        ["result", "index"],
        HpsDesignPointSelection(parameter_filter={"x": [4.0, 5.0, 6.0]}, eval_status=HpsJobEvaluationStatus.EVALUATED),
    )
