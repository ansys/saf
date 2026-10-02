.. _bdm_directories:

Work with folders using BDM Python API
##########################################

Simple usage
=============

Blob Data Management (BDM) Python API provides a way to handle directories in addition to individual files (BLOBs).
BDM Python API allows an ``EntityHandle`` object to reference a directory instead of a file.

Just as with files once you create an ``EntityHandle`` that references a directory you should not change its content.
You can read more about this general BDM Python API constraint :ref:`here <never-modify-referenced-data>`.  If this constraint is
problematic consider using a list or dictionary of ``EntityHandle`` objects instead of a directory.

To create an ``EntityHandle`` that references a directory, you can use the ``store()`` method on the storage scope.
For example:

.. code-block:: python

    my_directory_handle: EntityHandle = NO_ENTITY


    @transaction(self=StepSpec(upload=["my_directory_handle"]))
    def store_my_directory_handle(self):
        dirpath = self.storage_scope.get_storage_root() / "my_directory"
        dirpath.mkdir()
        (dirpath / "my_file.txt").write_text("some data")
        self.my_directory_handle = self.storage_scope.store(dirpath)

You can then access the content of the directory using the ``get_cached()`` and ``get_copy()`` methods on the storage scope.
For example to read a file located in the directory referenced by an ``EntityHandle``:

.. code-block:: python

    @transaction(self=StepSpec(download=["my_directory_handle"]))
    def get_my_file_from_directory_handle(self):
        dir_path = self.storage_scope.get_cached(self.my_directory_handle)
        filepath = dir_path / "my_file.txt"
        assert filepath.read_text() == "some data"

Access internals of a directory without using ``get_cached()`` or ``get_copy()`` methods
========================================================================================

BDM Python API storage scope provides methods to explore the structure of a directory referenced by an ``EntityHandle``.

Use ``get_child()``
-----------------------

Given an ``EntityHandle`` referencing a directory, you can get the ``EntityHandle`` of a file or directory immediately
contained in that directory using the ``get_child`` method on the storage scope.  ``get_child`` returns an ``EntityHandle``
object for a child file or directory given the original name of the child and the handle of the parent directory.

For example the following is a possible alternative of the example solution step code above:

.. code-block:: python

    @transaction(self=StepSpec(download=["my_directory_handle"]))
    def get_my_file_handle_from_directory_handle(self):
        my_file_handle = self.storage_scope.get_child(self.my_directory_handle, "my_file.txt")
        filepath = self.storage_scope.get_cached(my_file_handle)
        assert filepath.read_text() == "some data"

Use ``get_children()``
-----------------------

In addition to obtaining a single child handle using ``get_child()``, you can also obtain all the children of a
directory using the ``get_children()`` method on the storage scope.  ``get_children()`` returns a list of ``EntityHandle`` objects
for all the files and directories immediately contained in the directory referenced by a given ``EntityHandle``.

For example the following is a possible alternative of the example solution step code above:

.. code-block:: python

    @transaction(self=StepSpec(download=["my_directory_handle"]))
    def get_children_from_directory_handle(self):
        for entity_handle in self.storage_scope.get_children(self.my_directory_handle):
            if entity_handle.original_name == "my_file.txt":
                filepath = self.storage_scope.get_cached(entity_handle)
                assert filepath.read_text() == "some data"


Use the ``get_parent()`` method
-------------------------------

.. caution::
    Use this approach with caution.


The ``get_parent()`` method allows you to obtain the ``EntityHandle`` of the parent directory of a file or directory referenced by an ``EntityHandle``.

``get_parent()`` will return ``NO_ENTITY`` if the given ``EntityHandle`` refers to an entity stored immediately within a ``storage_root`` directory.

Its usage should normally be restricted to obtaining the original names of ancestor directories of an entity.
It is recommended that you avoid using ``get_parent()`` unless absolutely necessary as its behavior is somewhat ambiguous.

Just as an example of obtaining the original names of ancestor directories of an entity:

.. code-block:: python

    my_file: EntityHandle = NO_ENTITY


    @transaction(self=StepSpec(upload=["my_file"]))
    def store_my_directory_handle(self):
        dirpath = self.storage_scope.get_storage_root() / "my_directory"
        dirpath.mkdir()
        my_file = dirpath / "my_file.txt"
        my_file.write_text("some data")
        self.my_file = self.storage_scope.store(my_file)


    @transaction(self=StepSpec(download=["my_file"]))
    def check_ancestry(self):
        ancestry = []
        handle = self.my_file
        while handle != NO_ENTITY:
            ancestry.append(handle.original_name)
            handle = self.storage_scope.get_parent(handle)
        assert ancestry == ["my_file.txt", "my_directory"]

The content of the parent directory returned by ``get_parent()`` is undefined. If the store method has been applied to the parent directory or its ancestors
when the original handle was stored then all the content of the parent directory will be retained and will be accessible. If the store method has been applied
to descendent (file or subdirectory at any level) of the parent directory then that descendent will be retained and will be accessible. Whether any other
descendant entity is present will depend on whether garbage collection has been applied to the directory and is not defined.
Due to the ambiguous behaviour of ``get_parent()`` it needs to be used with great care. The ``get_children()`` method on the parent directory
may return differing numbers of children depending on which descendent entities have been destroyed directly or via garbage collection.

Rather than relying on navigating around directory structures using ``get_parent`` it is recommended that you keep track of specific files or directories by
storing their ``EntityHandle`` objects in step fields.


Use ``RecursiveDictionaryOfEntityHandles``
=======================================================

If you need to work with directory structures where you want to:

- Manipulate the structure: add, remove, rename files, reorganize subdirectories.
- Filter it
- Traverse the data
- Combine files from different storage scopes, BDM Python API provides

BDM Python API provides ``RecursiveDictionaryOfEntityHandles``, a specialized dictionary type that mirrors filesystem directory structures
using nested dictionaries of ``EntityHandle`` objects:

- Keys are strings representing file or directory names
- Values can be either:

  - An ``EntityHandle`` representing a file
  - Another ``RecursiveDictionaryOfEntityHandles`` representing a subdirectory

This allows you to create tree-like structures that mirror filesystem hierarchies while maintaining the immutability
benefits of BDM Python API for individual files.

Create a ``RecursiveDictionaryOfEntityHandles``
------------------------------------------------


Manual creation
~~~~~~~~~~~~~~~~

You can manually construct the dictionary structure by creating ``EntityHandle`` objects for individual files
and organizing them into nested dictionaries:

.. code-block:: python

    from ansys.saf.glow.solution import RecursiveDictionaryOfEntityHandles

    my_entities: RecursiveDictionaryOfEntityHandles = {}


    @transaction(self=StepSpec(upload=["my_entities"]))
    def manually_create_entities_dict(self):
        root_dir = self.storage_scope.get_storage_root()

        # Create files
        txt_file = root_dir / "root_file.txt"
        txt_file.write_text("This is a file in the root directory")
        json_file = root_dir / "level1_file.json"
        json_file.write_text('{"key": "value"}')

        # Store files and get their EntityHandles
        txt_file_handle = self.storage_scope.store(txt_file)
        json_file_handle = self.storage_scope.store(json_file)

        # Create a nested dictionary with the desired structure.
        self.my_entities = {
            "renamed_root_file.txt": txt_file_handle,  # Use a key that differs from the actual file name
            "subdir1": {"level1_file.json": json_file_handle},  # Introduce a subdirectory in the dictionary
        }

Note that this example creates a directory structure in the dictionary that differs from the actual
on-disk structure, introducing subdirectories and using keys for files that differ from their actual file names.
These keys are later used when recreating the directory structure during download. Hence, by simple dictionary manipulation,
you can easily reorganize and decide the name of the future copied files. You can use any string as a key in the dictionary,
as long as they are valid names for files and directories. An exception will be raised otherwise when trying to copy the
structure to disk. For early validation, you can use the ``validate_path_component()`` method from BDM Python API:

.. code-block:: python

    from ansys.bdm.api.recursive_dictionary import validate_path_component

    validate_path_component("invalid/name")


Automatic directory upload with ``store_to_dictionary()``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For convenience, you can automatically convert an entire directory structure into a ``RecursiveDictionaryOfEntityHandles``
using the ``store_to_dictionary()`` method:

.. code-block:: python

    my_entities: RecursiveDictionaryOfEntityHandles = {}


    @transaction(self=StepSpec(upload=["my_entities"]))
    def upload_directory_to_entities_dict(self):
        root_dir = self.storage_scope.get_storage_root()

        # Create a directory structure
        txt_file = root_dir / "root_file.txt"
        txt_file.write_text("This is a file in the root directory")
        json_file = root_dir / "subdir1" / "level1_file.json"
        json_file.parent.mkdir()
        json_file.write_text('{"key": "value"}')

        # Automatically convert the entire directory to RecursiveDictionaryOfEntityHandles
        self.my_entities = self.storage_scope.store_to_dictionary(root_dir)

The ``store_to_dictionary()`` method recursively walks through the directory structure, creating ``EntityHandle`` objects
for all files and preserving the directory hierarchy. For the snippet above, the resulting ``my_entities`` dictionary will have the following structure:

.. code-block:: none

    {
        "root_file.txt": <EntityHandle for root_file.txt>,
        "subdir1": {
            "level1_file.json": <EntityHandle for level1_file.json>
        }
    }

The ``store_to_dictionary()`` method also supports glob pattern filtering to selectively include files:

.. code-block:: python

    # Only store .txt files
    self.my_entities = self.storage_scope.store_to_dictionary(root_dir, glob="**/*.txt")

    # Store all files in a specific subdirectory
    self.my_entities = self.storage_scope.store_to_dictionary(root_dir, glob="subdir1/*")

    # self.my_entities will have the following structure
    # {
    #     "subdir1": {
    #         "level1_file.json": <EntityHandle for level1_file.json>
    #     }
    # }


Download from ``RecursiveDictionaryOfEntityHandles``
--------------------------------------------------------

You can download the entire directory structure (or a filtered subset) to disk using ``get_copy_from_dictionary()``:

.. code-block:: python

    @transaction(self=StepSpec(download=["my_entities"]))
    def download_directory_from_entities_dict(self):
        output_dir = self.storage_scope.get_storage_root() / "output_dir"

        # Assuming my_entities is a dictionary created previously with the following structure:
        # {
        #    "root_file.txt": <EntityHandle for root_file.txt>,
        #    "subdir1": {
        #        "level1_file.json": <EntityHandle for level1_file.json>
        #    }
        # }

        # Download all files and directories
        self.storage_scope.get_copy_from_dictionary(output_dir, self.my_entities)

        # Or download only specific files using a glob pattern
        self.storage_scope.get_copy_from_dictionary(output_dir, self.my_entities, glob="**/*.txt")

This recreates the directory structure at the specified location, preserving the hierarchy stored in the dictionary.
The method uses the dictionary keys for naming directories and files, not the ``original_name`` attributes stored in the ``EntityHandle`` objects.

This is how the ``output_dir`` would look after downloading all files from the previous example:

.. code-block:: text

    output_dir/
    ├── root_file.txt
    └── subdir1/
        └── level1_file.json

And if ``glob="**/*.txt"`` was used, only ``root_file.txt`` would be downloaded:

.. code-block:: text

    output_dir/
    └── root_file.txt


Manipulate ``RecursiveDictionaryOfEntityHandles``
----------------------------------------------------

Since ``RecursiveDictionaryOfEntityHandles`` is a dictionary, you can manipulate it in multiple ways and operate on its contents.

Access individual entities
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can access individual ``EntityHandle`` objects directly and use them with all standard BDM Python API operations:

.. code-block:: python

    @transaction(self=StepSpec(download=["my_entities"]))
    def access_individual_file(self):
        # Access the content of a file at any level
        content = self.storage_scope.get_text(self.my_entities["root_file.txt"])
        content = self.storage_scope.get_text(self.my_entities["subdir1"]["level1_file.json"])

Modify the structure
~~~~~~~~~~~~~~~~~~~~~

You can prune, reorganize, extend, or otherwise modify the dictionary structure:

.. code-block:: python

    @transaction(self=StepSpec(download=["my_entities"], upload=["my_entities"]))
    def manipulate_entities_dict(self):
        # Reduce to a subdirectory
        subset = self.my_entities["subdir1"]
        self.my_entities = subset

        # Add new entries
        new_file = self.storage_scope.get_storage_root() / "new_file.txt"
        new_file.write_text("New content")
        self.my_entities["new_file.txt"] = self.storage_scope.store(new_file)

        # Move files to different directories
        self.my_entities.update(self.my_entities.pop("subdir1"))

        # Rename a file by changing its dictionary key
        self.my_entities["renamed_root.txt"] = self.my_entities.pop("root_file.txt")

        # Remove entries
        del self.my_entities["old_file.txt"]


Use ``RecursiveDictionaryOfEntityHandles`` outside transactions
-------------------------------------------------------------------

All operations described above for solution transactions are also available when using ``RecursiveDictionaryOfEntityHandles`` from other storage scopes, such as the GLOW Client or product instances.

Usage from the GLOW client
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following example demonstrates usage from a Dash callback using the GLOW Client:

.. code-block:: python

    @callback(..., Input("button", "n_clicks"), State("url", "pathname"))  # Your output here
    def my_callback(n_clicks: int, project: MyMinimalSolution):
        step = project.steps.my_step
        root_dir = project.storage_scope.get_storage_root()
        txt_file = root_dir / "root_file.txt"
        txt_file.write_text("This is a file in the root directory")
        json_file = root_dir / "level1_file.json"
        json_file.write_text('{"key": "value"}')

        txt_file_handle = project.storage_scope.store(txt_file)
        json_file_handle = project.storage_scope.store(json_file)

        # Manually create the RecursiveDictionaryOfEntityHandles
        step.my_entities = {
            "renamed_root_file.txt": txt_file_handle,
            "subdir1": {"level1_file.json": json_file_handle},
        }

        # Automatically create the RecursiveDictionaryOfEntityHandles
        step.my_entities = project.storage_scope.store_to_dictionary(root_dir)

        # Access individual files
        content = project.storage_scope.get_text(step.my_entities["renamed_root_file.txt"])

        # Get a copy of the directory structure
        output_dir = project.storage_scope.get_storage_root() / "output_dir"
        project.storage_scope.get_copy_from_dictionary(output_dir, step.my_entities)

Usage from product instances
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following example demonstrates usage from product instances:

.. code-block:: python

    @transaction(self=StepSpec(download=["my_entities"]))
    @instance("my_product")
    def transfer_to_product(self, my_product: ProductInstanceManager):
        # Download from RecursiveDictionaryOfEntityHandles to product filesystem
        product_dir = my_product.storage_scope.get_storage_root() / "product_dir"
        my_product.storage_scope.get_copy_from_dictionary(product_dir, self.my_entities)


    @transaction(self=StepSpec(upload=["my_entities"]))
    @instance("my_product")
    def transfer_from_product(self, my_product: ProductInstanceManager):
        # Upload from product filesystem to RecursiveDictionaryOfEntityHandles
        product_dir = my_product.storage_scope.get_storage_root() / "product_dir"
        self.my_entities = my_product.storage_scope.store_to_dictionary(product_dir)


Mix entities from multiple storage systems
----------------------------------------------

A key advantage of ``RecursiveDictionaryOfEntityHandles`` is that it can contain ``EntityHandle`` objects from
multiple storage systems (transaction scope, client scope, product scope). You can create the dictionary in one
scope and then extend it in others.

The following example creates a directory within a product instance, extends it from the client and later in a second transaction.

.. code-block:: python

    @transaction(self=StepSpec(upload=["my_entities"]))
    @instance("my_product")
    def run_simulation(self, my_product: ProductInstanceManager):
        my_product.instance.do_something()
        # Store simulation results
        product_dir = my_product.storage_scope.get_storage_root() / "simulation_results"
        self.my_entities = my_product.storage_scope.store_to_dictionary(product_dir)

.. code-block:: python

    @callback(
        ..., Input("button", "n_clicks"), State("input-from-user", "value"), State("url", "pathname")  # Your output here
    )
    def my_callback(n_clicks: int, project: MyMinimalSolution, input_from_user: str):
        step = project.steps.my_step

        txt_file = project.storage_scope.get_storage_root() / "user_input.txt"
        txt_file.write_text(input_from_user)

        my_entities = step.my_entities
        my_entities["user_input.txt"] = project.storage_scope.store(txt_file)
        step.my_entities = my_entities

.. code-block:: python

    @transaction(self=StepSpec(download=["my_entities"], upload=["my_entities"]))
    def process_results(self):
        output_dir = self.storage_scope.get_storage_root() / "output_dir"
        process_simulation_and_user_input(self.my_entities, output_dir)
        self.my_entities["processed_results"] = self.storage_scope.store_to_dictionary(output_dir)

Afterwards, when using ``get_copy_from_dictionary()`` in any of these scopes, BDM Python API automatically retrieves the files from the appropriate storage systems.
