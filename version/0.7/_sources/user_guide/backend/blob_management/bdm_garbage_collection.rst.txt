.. _bdm_garbage_collection:

BDM garbage collection
######################

Delete files
==============

By default BDM uses a garbage collection mechanism to delete files that are no longer needed.
(The garbage collection mechanism can be switched off using the :envvar:`GLOW_BDM_GC_DISABLED` environment variable. Refer to the :ref:`disabling-gc` section.)
Files that are no longer referenced by any entity handle are automatically deleted by the garbage collector when there is no BDM activity.
To explicitly mark a file referenced by an entity handle for deletion, simply set the entity handle to ``NO_ENTITY`` ensuring the modified field is listed in the ``upload`` field of the transaction method's ``StepSpec``.

For example:

.. code-block:: python

    file_handle_to_delete: EntityHandle = NO_ENTITY


    @transaction(self=StepSpec(upload=["file_handle_to_delete"]))
    def delete_file(self) -> None:
        # mark the file for deletion by setting the field to NO_ENTITY
        self.file_handle_to_delete = NO_ENTITY


To remove files referenced in a list of entity handles, simply remove the entries from the list or set the list to an empty list if you
want to remove all files.  (do not forget to use the ``upload`` field of the ``StepSpec`` accordingly).

For example:

.. code-block:: python

    file_handles_to_delete: list[EntityHandle] = []


    @transaction(self=StepSpec(upload=["file_handles_to_delete"]))
    def delete_all_file_handles_from_list(self) -> None:
        # mark all the files for deletion by setting the list to an empty list.
        self.file_handles_to_delete = []


    @transaction(self=StepSpec(download=["file_handles_to_delete"], upload=["file_handles_to_delete"]))
    def pop_file_handle_from_list(self) -> None:
        # mark the last entry of the list for deletion.
        self.file_handles_to_delete.pop()

.. note::
   As mentioned above, the garbage collection is only triggered when there is no BDM activity.
   This is done to avoid removing files that are still being used elsewhere.
   It means that files won't be deleted if any transaction method is running or a dash callback using the storage scope is being executed

.. note::
   The BDM garbage collection only removes files that are no longer referenced by ***any*** entity handle.
   It means that if you have multiple entity handles referencing the same file, setting one of them to ``NO_ENTITY`` will not remove the file.
   Similarly, if you have one entity handle referencing a directory and another entity handle referencing a file within that directory,
   setting the file entity handle within the directory to ``NO_ENTITY`` will not remove the file since it is still referenced by the other entity handle.

.. _step-model-structures-supporting-bdm-garbage-collection:

Step model structures supporting BDM garbage collection
=========================================================

The BDM garbage collection mechanism determines the set of entities that need to be retained by locating all the ``EntityHandle`` objects stored in the
step objects of the current project. The process of locating this set of ``EntityHandle`` objects supports a wide range of data structures but is not
universal. When BDM garbage collection is enabled the BDM system will only retain files or directories referenced by ``EntityHandle`` objects stored in the
following step field types:

- ``EntityHandle``
- ``list[T]`` where ``T`` is one of the supported field types listed here
- ``set[T]`` where ``T`` is one of the supported field types listed here
- ``dict[K, V]`` where ``K`` and ``V`` are one of the supported field types listed here
- ``Tuple[T1, T2, ...]`` where ``EntityHandle`` objects are only contained in ``Ti`` that are one of the supported field types listed here
- ``BaseModel`` subclasses where ``EntityHandle`` objects are only contained in fields that are one of the supported field types listed here
- ``Union[T1, T2, ...]`` where ``EntityHandle`` objects are only contained in ``Ti`` that are one of the supported field types listed here
- ``T1 | T2 | ...`` where ``EntityHandle`` objects are only contained in ``Ti`` that are one of the supported field types listed here

.. _disabling-gc:

Disable garbage collection
==========================


In some cases, you may want to disable the garbage collection mechanism.
Solutions that manage their own file lifecycle and do not want the performance overheads of using the BDM garbage collector can disable the garbage collection mechanism.
To do that set the environment variable :envvar:`GLOW_BDM_GC_DISABLED` to ``True``.
When configured this way a solution will have to explicitly delete the file-system resources referenced by an entity handle that are about to be made inaccessible.
Applying the delete operation will avoid the solution consuming those resources indefinitely.
To do that, you need to call ``storage_scope.destroy`` with the entity handles that need to be removed, passed as arguments, as described in the BDM Python API documentation |storage-scope-destroy|_

.. code-block:: python

    file_handles_to_delete: list[EntityHandle] = []


    @transaction(self=StepSpec(upload=["file_handles_to_delete"]))
    def delete_all_file_handles_from_list(self) -> None:
        # remove explicitly all the files for deletion by calling destroy.
        # (must only be used when garbage collection is off!)
        self.storage_scope.destroy(*self.file_handles_to_delete)
