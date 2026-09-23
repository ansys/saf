.. _best_practices_backend_conventions:

Backend conventions
####################

This section covers the conventions that keep the SAF GLOW Engine backend stateless, predictable,
and deployable across multiple processes.


No module-level globals
========================

The GLOW API server is stateless—each request may be handled by a different process.
Module-level mutable state is never shared between requests and leads to subtle bugs
in multi-process deployments.

.. code-block:: python
   :caption: Incorrect — module-level mutable state

   # Breaks in multi-process deployment
   _cache = {}  # Module-level mutable state — never shared across processes


   class AnalysisStep(StepModel):
       temperature: float = 20.0

       @transaction(self=StepSpec(upload=["temperature"]))
       def run(self) -> None:
           _cache["last_run"] = self.temperature  # This is lost between requests

.. code-block:: python
   :caption: Correct — all state lives in step fields

   class AnalysisStep(StepModel):
       """Analysis step — state is persisted via step fields, not globals."""

       temperature: float = 20.0
       last_run_temperature: float = 0.0

       @transaction(self=StepSpec(download=["temperature"], upload=["last_run_temperature"]))
       def run(self) -> None:
           self.last_run_temperature = self.temperature


Never store session data in memory
====================================

For the same reason, never use in-memory session stores, caches, or singletons to hold
per-user or per-project data. SAF GLOW Engine persists all state through step fields—use them.

.. code-block:: python
   :caption: Incorrect — in-memory session store

   _sessions = {}  # Lost on restart, not shared across workers


   class SessionStep(StepModel):
       user_id: str = ""

       @transaction(self=StepSpec(download=["user_id"]))
       def track_user(self) -> None:
           _sessions[self.user_id] = {"logged_in": True}

.. code-block:: python
   :caption: Correct — session state in step fields

   class SessionStep(StepModel):
       """Session state persisted through GLOW step fields."""

       user_id: str = ""
       is_logged_in: bool = False

       @transaction(self=StepSpec(download=["user_id"], upload=["is_logged_in"]))
       def track_user(self) -> None:
           self.is_logged_in = True


File naming convention
=======================

Use the ``<name>_step.py`` naming convention for step model files. This makes it
immediately clear which modules define step models versus business logic or utilities.

.. code-block:: text
   :caption: Recommended file naming

   solution/
   ├── setup_step.py          ← step model
   ├── analysis_step.py       ← step model
   ├── results_step.py        ← step model
   ├── logic/
   │   ├── solver.py          ← business logic (not a step)
   │   └── post_process.py    ← business logic (not a step)
   └── definition.py          ← solution definition (StepsModel)


All fields must have defaults
==============================

Every field on a ``StepModel`` must have a default value. Fields without defaults cause
serialization failures when SAF GLOW Engine creates a new project.

.. code-block:: python
   :caption: Incorrect — missing defaults

   class AnalysisStep(StepModel):
       temperature: float  # No default — will fail on project creation
       results: list[float]  # No default — will fail on project creation

.. code-block:: python
   :caption: Correct — explicit defaults for every field

   class AnalysisStep(StepModel):
       """Analysis step model with explicit defaults."""

       temperature: float = 20.0
       pressure: float = 101.325
       results: list[float] = []
       notes: str | None = None

       @transaction(self=StepSpec(download=["temperature", "pressure"], upload=["results"]))
       def run(self) -> None:
           """Run the analysis computation."""
           self.results = [self.temperature * 1.5, self.pressure * 0.9]


Import strategy for heavy packages
====================================

Import heavy packages (NumPy, SciPy, PyAnsys clients) inside transaction methods if they
are used in only one place. Import at module level if used across multiple methods in the
same file.

This keeps module import time fast and avoids loading unnecessary dependencies during
SAF GLOW Engine's solution analysis phase.

.. code-block:: python
   :caption: Heavy import inside a single-use method

   class MeshStep(StepModel):
       """Step that uses NumPy only in one transaction."""

       mesh_data: list[float] = []

       @transaction(self=StepSpec(upload=["mesh_data"]))
       def generate_mesh(self) -> None:
           import numpy as np  # Imported here — used only in this method

           self.mesh_data = np.linspace(0, 1, 100).tolist()

.. code-block:: python
   :caption: Module-level import when used in multiple methods

   import numpy as np  # Used in multiple methods below


   class SimulationStep(StepModel):
       """Step where NumPy is used across several transactions."""

       input_data: list[float] = []
       normalized: list[float] = []
       statistics: dict[str, float] = {}

       @transaction(self=StepSpec(download=["input_data"], upload=["normalized"]))
       def normalize(self) -> None:
           arr = np.array(self.input_data)
           self.normalized = ((arr - arr.min()) / (arr.max() - arr.min())).tolist()

       @transaction(self=StepSpec(download=["input_data"], upload=["statistics"]))
       def compute_stats(self) -> None:
           arr = np.array(self.input_data)
           self.statistics = {"mean": float(arr.mean()), "std": float(arr.std())}
