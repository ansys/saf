.. _bdm_from_the_solution:

Use BDM from the solution
###########################

To work with persisted files within your solution, start by declaring an ``EntityHandle`` as a step field and assign it a default value of ``NO_ENTITY`` (both imported from ``ansys.saf.glow.solution``)
For example:

.. code-block:: python

    from ansys.saf.glow.solution import EntityHandle, NO_ENTITY


    class ExampleStep(StepModel):
        my_file_handle: EntityHandle = NO_ENTITY


Store a file
============

The ``NO_ENTITY`` default value of ``my_file_handle`` means that the entity handle does not reference any file yet.
Let's now create the file that we would like to persist as ``EntityHandle`` in ``my_file_handle``.

.. code-block:: python

    @transaction(self=StepSpec(upload=["my_file_handle"]))
    def store_my_file_handle(self):
        filepath = self.storage_scope.get_storage_root() / "my_file.txt"
        filepath.write_text("some data")
        self.my_file_handle = self.storage_scope.store(filepath)

Within ``store_my_file_handle``, we are accessing the method storage scope using ``self.storage_scope``.
The creation of ``EntityHandle`` from a file happens in two stages.
We first need to place the file within the storage scope directory.
To do that we are using ``self.storage_scope.get_storage_root()`` which is returning the directory that can be used to stage files.
Then we are calling ``self.storage_scope.store()`` to create an ``EntityHandle`` from the given file on disk.
The created entity handle is finally assigned to the step field ``self.my_file_handle``.

.. note::
   Do not forget to use the step spec ``upload=["my_file_handle"]`` after assigning the entity handle to the step field, or it won't be persisted and the file would be removed.


Access the stored file
========================

To access the file referenced by ``my_file_handle``, we again need to use the method storage scope.

.. code-block:: python

    @transaction(self=StepSpec(download=["my_file_handle"]))
    def access_my_file_handle(self):
        filepath = self.storage_scope.get_cached(self.my_file_handle)
        content = filepath.read_text()
        assert content == "some data"


``self.storage_scope.get_cached()`` realizes the data to the local filesystem if needed and returns a path to the cached or original file.
The path can then be used to access the content of the file.

.. warning::
    The ``EntityHandle`` is intended to represent an immutable value.
    The file returned by ``get_cached()`` may point to a cached or even the original file.
    Callers must not modify the file on disk or undefined behavior, including class 3 errors, may occur.
    If the caller needs to modify the file, consider using ``get_copy()``, or copying the file before modifying it.


Store a directory
=================

As mentioned earlier, an ``EntityHandle`` is a handle to an entity stored by a BDM provider.
The entity can be either a file or a directory.
To create an ``EntityHandle`` out of a directory, the same approach used for files is used.

.. code-block:: python

    @transaction(self=StepSpec(upload=["my_directory_handle"]))
    def store_my_directory_handle(self):
        dirpath = self.storage_scope.get_storage_root() / "my_directory"
        dirpath.mkdir()
        (dirpath / "my_file.txt").write_text("some data")
        self.my_directory_handle = self.storage_scope.store(dirpath)


To explore the structure of the directory referenced by an ``EntityHandle`` , we can use ``get_children()``, ``get_child()``, ``get_parent`` etc. on the storage scope.


.. code-block:: python

    @transaction(self=StepSpec(download=["my_directory_handle"]))
    def get_my_file_from_directory_handle(self):
        my_file_handle = self.storage_scope.get_child(self.my_directory_handle, "my_file.txt")
        filepath = self.storage_scope.get_cached(my_file_handle)
        assert filepath.read_text() == "some data"


Product instance manager storage scope
=======================================

So far we have been using the method storage scope to interact with entity handles using ``self.storage_scope``.
A product instance manager has a storage scope to facilitate the optimized transfer of files and directories between the GLOW server running your solution and the actual product being managed.
(A product instance manager is the object used to access a product on methods decorated with ``@instance`` or ``@create_instance``.)

Methods each have a separate storage scope, product instances each have a separate storage scope.
Each storage scope (for product or method) is implemented as a completely separate entity.
For example each storage scope may use its own file system.

The ``storage_scope`` property of a product instance manager is implemented so its methods use file paths that are only valid in the context of the product.
For example the ``store`` method expects file paths returned by the product api and the ``get_cached`` method returns file paths that can be passed to the product api.
Code that bypasses the product instance manager storage scope when interacting with the product API will not function correctly across SAF GLOW Engine's various deployment types.

As a concrete example, let's picture a cloud deployment where the solution is deployed on Linux and the product is running in Windows.
Using ``self.storage_scope.get_cached(self.my_file_handle)`` would resolve the path to the Linux filesystem: ``/projects/<project_id>/bdm/method_abcdefg/my_file.txt``.
The problem is that this path is not available from the product Windows filesystem.
To overcome this issue, use the product storage scope ``my_product_manager.storage_scope.get_cached(self.my_file_handle)`` which would resolve the path to the Windows filesystem: ``c:\project_files\<project_id>\bdm\method_abcdefg\my_file.txt``

Since the product manager is running within the method and not on the remote product itself, you must also be aware that it cannot be used to manipulate (read, write, or access in any way) files or directories on the remote product.
For example, doing ``(my_product_manager.get_storage_root() / "wrong_file.txt").write_text("THIS IS PROHIBITED!")`` is prohibited.
Instead, you should create the entity using the method storage scope, then use the product storage scope to access it.
The example below illustrates this:
the file handle is created using the method storage scope, then the file handle is used by the product storage scope so that it is resolved properly on the product context.

.. code-block:: python

    @transaction(self=StepSpec(upload=["my_file_handle"]))
    @instance("my_product_manager")
    def product_open_file(self, my_product_manager: MyProductInstanceManager):
        my_filepath = self.storage_scope.get_storage_root() / "my_file.txt"
        my_filepath.write_text("some data")
        self.my_file_handle = self.storage_scope.store(my_filepath)
        filepath_on_product = my_product_manager.storage_scope.get_cached(self.my_file_handle)
        my_product_manager.instance.open(filepath_on_product)


