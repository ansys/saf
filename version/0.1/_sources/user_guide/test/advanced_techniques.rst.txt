.. _test_advanced_techniques:

Advanced techniques
###################

Reuse code for setting up project state for tests
=================================================

``client_project`` always returns a freshly created new project of your solution. However, you may want to reuse
some code to set up a specific project state for multiple tests. For example, you may want to create a project with
fields already set, transactions executed, or with some files already uploaded. In that case, you can combine it with another
pytest fixture:

.. code-block:: python

    @pytest.fixture
    def initiated_project(client_project: MySolution) -> MySolution:
        # Set up the project state
        client_project.steps.first_step.first_arg = 10.0
        client_project.steps.first_step.second_arg = 20.0
        client_project.steps.first_step.calculate()
        return client_project


    def test_using_setup_project_state(initiated_project: MySolution):
        first_step = initiated_project.steps.first_step
        assert first_step.result == 30.0


    def test_another_using_setup_project_state(initiated_project: MySolution):
        first_step = initiated_project.steps.first_step
        assert first_step.first_arg == 10.0
        assert first_step.second_arg == 20.0
