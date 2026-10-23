.. _best_practices_data_model_rules:

################
Data model rules
################

.. admonition:: Best practice
   :class: best-practice

   - Every field needs a schema—use typed Pydantic fields with defaults.
   - Prefer Pydantic ``BaseModel`` subclasses over plain ``dict`` for structured data with a predictable shape.
   - Use ``EntityHandle`` for files and folders.
   - Keep field names stable—they become part of the migration contract.

.. code-block:: python
   :caption: Well-typed step model with diverse field types

   from enum import Enum
   from pydantic import BaseModel
   from ansys.bdm.api import EntityHandle, NO_ENTITY, RecursiveDictionaryOfEntityHandles
   from ansys.saf.glow.solution import StepModel

   class SolverType(Enum):
       """Available solver types."""

       DIRECT = "direct"
       ITERATIVE = "iterative"

   class MeshSettings(BaseModel):
       """Mesh configuration — structured data with a predictable shape."""

       element_size: float = 1.0
       refinement_level: int = 2

   class BeamBendingStep(StepModel):
       """Step model with representative field types."""

       # Primitives with defaults
       length: float = 1000.0                     # mm
       diameter: float = 50.0                      # mm
       load: float = 10e3                           # N
       num_elements: int = 4
       is_nonlinear: bool = False

       # Enum
       solver: SolverType = SolverType.DIRECT

       # Nested Pydantic model (preferred over plain dict)
       mesh: MeshSettings = MeshSettings()

       # Collections
       deflection: list[float] = []
       material_properties: dict[str, float] = {}

       # BDM handles for files and directories
       result_file: EntityHandle = NO_ENTITY
       report_files: list[EntityHandle] = []
       output_directory: RecursiveDictionaryOfEntityHandles = RecursiveDictionaryOfEntityHandles()

       # Optional
       notes: str | None = None

.. _best_practices_supported_field_types:

Supported field types
=====================

- Primitives: ``int``, ``float``, ``str``, ``bool``, ``bytes``
- Collections: ``list[T]``, ``dict[str, T]``, ``tuple[...]``
- Pydantic models: Any ``BaseModel`` subclass
- Special SAF types: ``EntityHandle``, ``RecursiveDictionaryOfEntityHandles``
- Enums: Any ``enum.Enum`` subclass
- Optional: ``T | None``
