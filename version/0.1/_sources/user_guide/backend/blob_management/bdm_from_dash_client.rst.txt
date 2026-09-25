.. _bdm_from_dash_client:

Use BDM from the client (Dash)
#####################################

Client storage scope
====================

To access or create an ``EntityHandle`` from the client, the same principles apply: use the storage scope.
The client storage scope is available on the project object, using ``project.storage_scope``

.. code-block:: python

    @callback(State("url", "pathname"))
    def store_file_handle(project: MySolution):
        storage_scope = project.storage_scope
        filepath = storage_scope.get_storage_root() / "my_file.txt"
        filepath.write_text("some data")
        project.steps.example_step.my_file_handle = storage_scope.store(filepath)
        ...


    @callback(State("url", "pathname"))
    def access_file_handle(project: MySolution):
        filepath = project.storage_scope.get_cached(project.steps.example_step.my_file_handle)
        assert filepath.read_text() == "some data"
        ...



Entity handle URL
==================

In some cases, you may need to be able to generate a URL from an entity handle so that you can pass the URL to an UI component to render or process the entity.
To do that you can call ``get_entity_url(entity_field_name)`` on the step by providing the name of the entity handle field.

.. code-block:: python

    entity_handle_url = project.steps.my_step.get_entity_url("my_file_handle")


