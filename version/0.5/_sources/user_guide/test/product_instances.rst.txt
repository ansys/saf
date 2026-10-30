.. _test_product_instances:

Product instance testing
########################

Product instance testing is done using the ``mock_product_instance`` fixture.

The ``mock_product_instance`` fixture enables you to test transactions that use product instances without requiring
the products to be running. This fixture mocks both the product instance management system
(PIM Light Server or HPS) and the product instance itself, allowing you to test your solution's integration with
Ansys products like AEDT, Mechanical, or custom product instances.

The fixture supports both shared and unshared product instances, enabling comprehensive testing of different
product instance usage patterns in your solution.

The only thing required to implement is the object returned by the ``.instance`` property of the product manager,
which is typically a PyAnsys client object. You need to create a mock class that simulates the behavior of this client object,
implementing the methods and properties that your transactions will use. See the examples below for more details.

.. admonition:: Warning
   :class: warning

   **Only supports BDM-based Product Managers.**


Example setup
==============

For the examples, we are going to use a minimal step that uses an instance of AEDT Maxwell 2D to process an input file.

.. code-block:: python

    from ansys.saf.product_manager.aedt import Maxwell2DManager


    class MyProductInstance(StepModel):

        input_file: EntityHandle = NO_ENTITY
        output_file: EntityHandle = NO_ENTITY

        @transaction(self=StepSpec())
        @create_instance("m2d", Maxwell2DManager)
        def launch_product(self, m2d: Maxwell2DManager) -> None:
            m2d.initialize()

        @transaction(self=StepSpec())
        @instance("m2d")
        def use_product(self, m2d: Maxwell2DManager) -> str:
            return m2d.instance.aedt_version_id

        @transaction(self=StepSpec(download=["input_file"], upload=["output_file"]))
        @instance("m2d")
        def use_product_files(self, m2d: Maxwell2DManager) -> None:
            filepath_on_product = m2d.storage_scope.get_cached(self.input_file).as_posix()
            output_data = str(m2d.instance.process_input_file(filepath_on_product))
            self.output_file = m2d.storage_scope.store_stream(output_data.encode())

        @transaction(self=StepSpec())
        def use_unshared_product_instance(self) -> str:
            with Maxwell2DManager() as m2d:
                return m2d.instance.aedt_version_id

Mock setup
============

First, you need to create a mock client class that simulates the behavior of the real product client:

.. code-block:: python

    class MyMockAedtClient:
        @property
        def aedt_version_id(self) -> str:
            return "2024.2"

        def process_input_file(self, input_file: str) -> str:
            return Path(input_file).read_text() + " [PROCESSED]"

Then, you need to parametrize the fixture ``mock_product_instance`` in your test function, class or module,
specifying the product instance manager to mock and the mock client class to use. For example:

.. code-block:: python

    from ansys.saf.product_manager.aedt import Maxwell2DManager

    # MODULE LEVEL
    pytestmark = [pytest.mark.parametrize("mock_product_instance", [{Maxwell2DManager: MyMockAedtClient}], indirect=True)]


    # CLASS LEVEL
    @pytest.mark.parametrize("mock_product_instance", [{Maxwell2DManager: MyMockAedtClient}], indirect=True)
    class TestProduct:
        def test_create_and_use_shared_product_instance(self, client_project: MySolution):
            # Test implementation
            pass


    # TEST LEVEL
    @pytest.mark.parametrize("mock_product_instance", [{Maxwell2DManager: MyMockAedtClient}], indirect=True)
    def test_create_and_use_shared_product_instance(client_project: MySolution):
        # Test implementation
        pass


Shared product instance testing
================================

Test shared product instances that are created once and reused across multiple transactions:

.. code-block:: python

    from ansys.saf.product_manager.aedt import Maxwell2DManager


    @pytest.mark.parametrize("mock_product_instance", [{Maxwell2DManager: MyMockAedtClient}], indirect=True)
    def test_create_and_use_shared_product_instance(client_project: MySolution):
        # Launch the product instance
        client_project.steps.my_product_instance.launch_product()

        # Use the shared instance in subsequent transactions
        version = client_project.steps.my_product_instance.use_product()
        assert version == "2024.2"


Unshared product instance testing
=================================

Test unshared product instances that are created and destroyed within a single transaction:

.. code-block:: python

    @pytest.mark.parametrize("mock_product_instance", [{Maxwell2DManager: MyMockAedtClient}], indirect=True)
    def test_unshared_product_instance(client_project: MySolution):
        # Use an unshared product instance
        version = client_project.steps.my_product_instance.use_unshared_product_instance()
        assert version == "2024.2"

File processing with product instances
======================================

Test file operations that involve product instances processing input files and generating outputs:

.. code-block:: python

    @pytest.mark.parametrize("mock_product_instance", [{Maxwell2DManager: MyMockAedtClient}], indirect=True)
    def test_product_instance_file_processing(client_project: MySolution):
        # Create input file
        random_input_data = "test input data"
        client_project.steps.my_product_instance.input_file = client_project.storage_scope.store_stream(
            random_input_data.encode()
        )

        # Launch product and process file
        client_project.steps.my_product_instance.launch_product()
        client_project.steps.my_product_instance.use_product_files()

        # Verify processed output
        output_content = client_project.storage_scope.get_text(client_project.steps.my_product_instance.output_file)
        assert output_content == "test input data [PROCESSED]"

Multiple product instances
==========================

You can also test multiple different product instances in a single test. For example, let's consider a second step that uses a Mechanical instance:

.. code-block:: python

    from ansys.saf.product_manager.mechanical import MechanicalManager


    class AnotherProductInstance(StepModel):

        @transaction(self=StepSpec())
        @create_instance("mechanical", MechanicalManager)
        def launch_and_use_second_product(self, mechanical: MechanicalManager) -> list[str]:
            mechanical.initialize()
            return mechanical.instance.list_files()

Then, you can parametrize the fixture with a dictionary that includes key-values for both products:

.. code-block:: python

    from ansys.saf.product_manager.aedt import Maxwell2DManager
    from ansys.saf.product_manager.mechanical import MechanicalManager


    class MyMockMechanicalClient:

        def list_files(self) -> list[str]:
            return ["file1.txt", "file2.txt"]


    @pytest.mark.parametrize(
        "mock_product_instance",
        [
            {
                Maxwell2DManager: MyMockAedtClient,
                MechanicalManager: MyMockMechanicalClient,
            }
        ],
        indirect=True,
    )
    def test_multiple_product_instances(client_project: MySolution):
        # Use AEDT product instance
        client_project.steps.my_product_instance.launch_product()
        aedt_version = client_project.steps.my_product_instance.use_product()
        assert aedt_version == "2024.2"

        # Use Mechanical product instance
        mechanical_files = client_project.steps.another_product_instance.launch_and_use_second_product()
        assert mechanical_files == ["file1.txt", "file2.txt"]
