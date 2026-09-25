.. _test_other_fixtures:

Other fixtures
##############

Configure the solution API
===========================

You can control the solution's environment and configuration in your tests using ``configure_solution``
fixture, which allows you to set environment variables for each test session by passing a dictionary
of environment variables, simulating different deployment scenarios or enabling debug features.

To use this in a test, you can combine it with ``pytest.mark.parametrize``. For example:

.. code-block:: python

    @pytest.mark.parametrize("configure_solution", [{"GLOW_DEBUG": "True"}], ids=["with_debug"], indirect=True)
    def test_configuring_solution(client_project):
        # Your test logic here
        ...

This will set the ``GLOW_DEBUG`` environment variable to ``True`` for the test, enabling debug mode
and more detailed error reporting. You can use this fixture at any scope: module, class, single test...

.. code-block:: python

    @pytest.mark.parametrize("configure_solution", [{"GLOW_DEBUG": "True"}], ids=["with_debug"], indirect=True)
    def MyGroupOfTests():
        def test_one(self, client_project):
            # Your test logic here
            ...


    pytestmark = [
        pytest.mark.parametrize("configure_solution", [{"GLOW_DEBUG": "True"}], ids=["with_debug"], indirect=True)
    ]


    def test_one(client_project):
        # Your test logic here
        ...


    def test_second(client_project):
        # Your test logic here
        ...


In all cases, configuration is undone at the end of the last test of the scope, making sure that it not pollutes other tests.


Project information
====================

``project_id``: a fixture that extracts the project ID from the project used in ``client_project``.

.. code-block:: python

    def test_project_id(client_project: MySolution, project_id: str):
        assert project_id == client_project.url.split("/projects/")[1]

``project_name``: a fixture that extracts the project name from the project used in ``client_project``.

.. code-block:: python

    def test_project_name(client_project: MySolution, project_id: str, project_name: str):
        expected_name = f"projects/{project_id}"
        assert project_name == expected_name

``project_display_name``: a fixture that extracts the project display name from the project used in ``client_project``.

.. code-block:: python

    def test_project_display_name(client_project: MySolution, project_display_name: str):
        assert project_display_name == client_project.project_display_name


File management
================

``project_files_dir``: a fixture that returns the directory path for project files used by the Solution API.

.. code-block:: python

    from pathlib import Path


    def test_project_files_dir(client_project: MySolution, project_files_dir: Path):
        # Call a transaction that writes a file
        client_project.steps.my_step.write_file(name="my_file.txt", content="my content")

        # Check if the file exists
        assert (project_files_dir / "my_file.txt").read_text() == "my content"


Logging utilities
==================

``solution_logs``: a fixture that sets up a temporary log file and logger for solution-related logs during tests.

.. code-block:: python

    def test_solution_logs(client_project: MySolution, solution_logs: Path):
        # Call a transaction that logs a message
        client_project.steps.my_step.transaction_that_logs_something(log_msg="my msg")

        # Check if the message is present in the logs
        assert "my msg" in solution_logs.read_text()

``is_msg_in_logs``: a fixture that provides a utility to check if a specific message appears in the solution logs.

.. code-block:: python

    from collections.abc import Callable


    def test_is_msg_in_logs(client_project: MySolution, is_msg_in_logs: Callable[[str], bool]):
        # Call a transaction that logs a message
        client_project.steps.my_step.transaction_that_logs_something(log_msg="Log message for testing")

        # Check if the message is present in the logs
        assert is_msg_in_logs("Log message for testing")
        assert not is_msg_in_logs("This message should not be in the logs")
