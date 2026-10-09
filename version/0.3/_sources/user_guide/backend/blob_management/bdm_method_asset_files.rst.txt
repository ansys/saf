.. _bdm_method_asset_files:

Access asset files using BDM
##############################

:dfn:`Method asset files` are files used by transaction methods but are not modified or deleted by those methods. Method asset files are:

- Part of a solution
- Shipped with a packaged solution for deployment
- Common to all projects of a solution

An example of a method asset file is a script that is passed to a solver.
Method asset files often contain Ansys intellectual property and are typically shipped in encrypted form. SAF GLOW Engine manages the decryption of these files for transaction methods that reference the files.


Method asset entity handles
===========================

To access method asset files within a transaction method, you need to retrieve the ``EntityHandle`` referencing the asset file by using the method ``get_asset_entity_handle(asset_relative_path)`` on ``self.transaction`` within the transaction method.
You can then use BDM Python API on the asset entity handle to read its content.

.. code-block:: python

  @transaction(self=StepSpec())
  def access_and_use_method_asset_file(self) -> None:
      # considering an asset file located in method_assets/my_asset.txt.encrypted
      asset_handle = self.transaction.get_asset_entity_handle("my_asset.txt")
      asset_content = self.storage_scope.get_text(asset_handle)
      ...
      call_my_solver(asset_content)


The argument of ``get_asset_entity_handle`` refers to the relative path of an asset from the ``method_assets`` directory.
It could refer to a file or a directory.

.. note::
  For encrypted files, the ``.encrypted`` suffix on the file name should be omitted.


Asset entity handles mechanism
=================================

The files referenced by the ``get_asset_entity_handle()`` method are located in a ``method_assets`` directory in the solution source tree.
The ``method_assets`` directory referenced by a particular field is the last (innermost) ``method_assets`` directory located in the directories on the path of the step definition Python file.

Let's consider the following directory structure:

.. code-block:: text

  - my_solution
    - method_assets
      - my_file.txt
    - my_step_definitions
      - method_assets
        - my_file.txt
      - step1.py
    - step2.py


In this example:

* ``self.transaction.get_asset_entity_handle(my_file)`` in ``step1.py`` references the file ``solution/my_step_definitions/method_assets/my_file.txt``.
* A similar definition in ``step2.py`` references the file ``solution/method_assets/my_file.txt``.

.. attention::
  The preceding file structure is only an example and is not a recommended structure. The recommended structure is to have a single ``method_assets`` directory located in the ``ansys.solutions.<solution>`` directory.


Reference encrypted asset files
==================================

To reference an encrypted asset file, the same logic applies.
Simply use ``self.transaction.get_asset_entity_handle("my_encrypted_asset.txt")`` where ``my_encrypted_asset.txt`` references a file named ``my_encrypted_asset.txt.encrypted`` located in the following place:

.. code-block:: text

  - my_solution
   - method_assets
     - my_encrypted_asset.txt.encrypted
   - step1.py

To support decryption, if a key was used to encrypt the assets, the ``method_assets`` directory must contain a ``glow_assets_metadata.json`` file that contains a JSON
dictionary with a ``translator`` key. The value for this key is the decryption password for the encrypted assets in the
``method_assets`` directory. If instead the assets were automatically decrypted (for example, using SAF Desktop Installer without encryption key), no file is needed.

An example of the content ``glow_assets_metadata.json`` file is:

.. code-block:: json

  {
    "translator": "my_password"
  }

To avoid leaking the Ansys intellectual property from the encrypted file, the following design has been implemented:

* For encrypted files: ``get_stream``, ``get_bytes`` and ``get_text`` will decrypt the referenced file into memory only and not write the file to disk.
* For encrypted files: ``get_cached`` will write the decrypted data to a temporary location within the project directory.
* For decrypted files: ``get_stream``, ``get_bytes`` and ``get_text`` will read the data directly from the method_assets directory.

..
  _TODO: move the content from the solution developers guide related to obfuscation to this doc and add a link here


Execute Python code from method asset files
=============================================

You can dynamically import and run code from a method asset file within a transaction method. For example, if you have a Python file named ``addition_module.py`` in the ``method_assets`` directory that contains a function named ``add_function``, you can import and execute it as follows:

.. code-block:: python

    @transaction(self=StepSpec())
    def run_python_code_from_asset(self, first_arg: int, second_arg: int) -> int:
        asset_handle = self.transaction.get_asset_entity_handle("addition_module.py")

        spec = importlib.util.spec_from_file_location(
            "addition_module",
            self.storage_scope.get_cached(asset_handle).as_posix(),
        )
        if not spec or not spec.loader:
            raise ValueError("Failed to load addition_module")
        addition_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(addition_module)

        return addition_module.add_function(first_arg, second_arg)


