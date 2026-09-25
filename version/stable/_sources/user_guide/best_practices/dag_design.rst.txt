.. _best_practices_dag_design:

DAG design
##########

SAF builds a Directed Acyclic Graph (DAG) from ``StepSpec`` declarations. Understanding
how the DAG works is key to designing efficient, predictable solutions.


How the DAG works
==================

Each ``@transaction`` declares which fields it reads (``download``) and writes
(``upload``). GLOW uses these declarations to build a dependency graph:

- ``download`` fields are **upstream** (inputs).
- ``upload`` fields are **downstream** (outputs).
- When an upstream field changes, all downstream dependents are automatically marked
  ``OUTOFDATE``.

.. image:: /_static/images/dag_fundamentals.svg
   :align: center
   :width: 80%
   :alt: Diagram showing how StepSpec download and upload fields form a directed acyclic graph

.. code-block:: python
   :caption: Single-step DAG — ``temperature`` is read and ``results`` is written

   @transaction(self=StepSpec(download=["temperature"], upload=["results"]))
   def compute(self) -> None:
       self.results = [self.temperature * 1.5]

.. code-block:: python
   :caption: Cross-step DAG — ``analysis`` reads from ``setup``

   # In AnalysisStep:
   @transaction(
       self=StepSpec(upload=["solver_result"]),
       setup=StepSpec(download=["temperature", "pressure"]),
   )
   def solve(self, setup: SetupStep) -> None:
       self.solver_result = setup.temperature * setup.pressure

In this example, if the user changes ``setup.temperature``, the framework marks
``analysis.solver_result`` as ``OUTOFDATE`` automatically.


Keep dependencies within a step
=================================

When a transaction reads and writes fields on the same step, the DAG stays simple and
self-contained. Prefer this pattern when the data does not need to flow across steps.

.. code-block:: python
   :caption: Self-contained step — input and output on the same step

   class BeamStep(StepModel):
       """All fields belong to the same concern."""

       length: float = 1.0
       load: float = 100.0
       deflection: float = 0.0

       @transaction(self=StepSpec(download=["length", "load"], upload=["deflection"]))
       def solve(self) -> None:
           self.deflection = (self.load * self.length**3) / (3 * 200e9)


Declare cross-step reads explicitly
=====================================

When data must flow between steps, declare the dependency explicitly via the
``@transaction`` parameter list. Never access another step's fields by importing
the step instance directly — GLOW cannot track implicit reads.

.. code-block:: python
   :caption: Correct — explicit cross-step read via StepSpec

   @transaction(
       self=StepSpec(upload=["summary"]),
       setup=StepSpec(download=["temperature"]),
       analysis=StepSpec(download=["solver_result"]),
   )
   def generate_summary(self, setup: SetupStep, analysis: AnalysisStep) -> None:
       self.summary = f"T={setup.temperature}, Result={analysis.solver_result}"


Keep the DAG shallow
=====================

Deep dependency chains cause cascading recomputations: a single change at the top
invalidates every step below it. Keep the DAG as flat as possible.

.. image:: /_static/images/dag_depth.svg
   :align: center
   :width: 80%
   :alt: Diagram comparing a shallow DAG with a deep chain to illustrate cascading recomputation risks

.. code-block:: python
   :caption: Shallow — two steps read directly from setup (no relay)

   class AnalysisStep(StepModel):
       solver_result: float = 0.0

       @transaction(
           self=StepSpec(upload=["solver_result"]),
           setup=StepSpec(download=["temperature"]),
       )
       def solve(self, setup: SetupStep) -> None:
           self.solver_result = setup.temperature * 1.5


   class ResultsStep(StepModel):
       report: str = ""

       @transaction(
           self=StepSpec(upload=["report"]),
           setup=StepSpec(download=["temperature"]),
       )
       def generate_report(self, setup: SetupStep) -> None:
           self.report = f"Report for T={setup.temperature}"


Sketch the DAG before coding
==============================

Before writing any step code, draw the dependency graph on paper or a whiteboard. This
helps you identify:

- Which fields are shared between steps.
- Where the deepest chains are.
- Whether a step can be split or merged to simplify the graph.

.. code-block:: text
   :caption: Example DAG sketch for a thermal-structural workflow

   SetupStep
   ├── temperature ──────► ThermalStep.heat_source
   ├── geometry    ──────► ThermalStep.mesh
   └── geometry    ──────► StructuralStep.mesh

   ThermalStep
   └── temperature_field ─► StructuralStep.thermal_load

   StructuralStep
   └── stress_result      (terminal — no downstream)

Translating this sketch into ``StepSpec`` declarations makes the implementation
straightforward and the dependency graph predictable.
