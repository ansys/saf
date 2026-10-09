.. _bdm_best_practice:

.. _best_practices_bdm:

BDM best practices
###################
When working with the BDM feature in your solution, consider the following best practices to ensure optimal performance and maintainability:

.. _never-modify-referenced-data:

Never modify data referenced by an entity handle
---------------------------------------------------

Once you have created an ``EntityHandle`` object referring to a file or directory solution code should never modify the content of
the referenced file or directory. The BDM system relies on the immutability of the data referenced by an ``EntityHandle`` to
enable the efficient caching and transfer of file and directories.

For example the following Solution step code is incorrect:

.. code-block:: python

    result: EntityHandle = NO_ENTITY


    @transaction(self=StepSpec(upload=["result"]))
    def solve(self):
        result_file = self.storage_scope.storage_root / "result.txt"
        result_file.write_text("data that should not change")
        self.result = self.storage_scope.store(result_file)


    @transaction(self=StepSpec(download=["result"]))
    def modify(self):
        result_path = self.storage_scope.get_cached(self.result)
        result_path.write_text("modified data that should not happen")

The file referenced by the path returned by ``get_cached()`` must not be modified as shown in the ``modify`` method above.

It is important to be careful when writing iterative transaction methods that may update the content of a file.
For example the following code is incorrect:

.. code-block:: python

    result: EntityHandle = NO_ENTITY


    @transaction(self=StepSpec(upload=["result"]))
    @long_running
    def solve(self):
        result_file = self.storage_scope.storage_root / "result.txt"
        solve_output_path = Path("solver") / "output" / "data.txt"
        background_solve()
        while True:
            result_file.write_text(solve_output_path.read_text())
            self.result = self.storage_scope.store(result_file)
            time.sleep(5)
            self.transaction.upload("result")

Each iteration of the loop replaces the content of the file referenced by the path ``result_file``.
This path does not change and is mapped into the ``EntityHandle`` object ``self.result``.
As a result each iteration of the loop modifies the content of the file referenced by the handle created by
previous iterations of the loop.
This is incorrect and may lead to undefined behavior.

To correct the code above, ensure that each iteration of the loop creates an entity to store the result:

.. code-block:: python

    result: EntityHandle = NO_ENTITY


    @transaction(self=StepSpec(upload=["result"]))
    @long_running
    def solve(self):
        result_file = self.storage_scope.storage_root / "result.txt"
        solve_output_path = Path("solver") / "output" / "data.txt"
        background_solve()
        while True:
            self.result = self.storage_scope.store_stream(solve_output_path.read_bytes())
            time.sleep(5)
            self.transaction.upload("result")

The call to ``store_stream`` creates a new unique file each time it is called so that the files referenced by
``EntityHandle`` objects created in previous iterations of the loop are not modified.

Ensure that fields containing ``EntityHandle`` support BDM garbage collection
------------------------------------------------------------------------------

Make sure that any field that stores ``EntityHandle`` objects is of a type supported by the BDM garbage collection mechanism
as listed :ref:`here <step-model-structures-supporting-bdm-garbage-collection>`.
