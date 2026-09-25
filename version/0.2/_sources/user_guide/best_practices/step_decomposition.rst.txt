.. _best_practices_step_decomposition:

########################
Step decomposition
########################

This section explains how to divide your workflow into steps and how steps relate to
UI pages.


One step per logical concern
=============================

Prefer one step per logical concern (setup, solving, results). Each step should own a
cohesive set of fields that belong to the same phase of the workflow.

.. image:: /_static/images/step_decomposition.svg
   :align: center
   :width: 80%
   :alt: Diagram showing how a workflow is decomposed into individual steps, each owning a logical concern

Start with a one-to-one mapping between steps and UI pages, but keep the relationship
flexible:

- One step can span multiple pages (for example, configuration, execution, and results
  views over the same data).
- A single page can aggregate content from multiple steps.

.. code-block:: python
   :caption: Example — three steps, each owning a logical concern

   class SetupStep(StepModel):
       """Owns geometry and material configuration."""

       length: float = 1000.0
       diameter: float = 50.0
       material: str = "steel"

   class SolvingStep(StepModel):
       """Owns solver execution and progress tracking."""

       solver_type: str = "direct"
       progress: float = 0.0
       is_running: bool = False

   class ResultsStep(StepModel):
       """Owns computed outputs and report generation."""

       max_stress: float = 0.0
       deflection: list[float] = []
       report_ready: bool = False


.. _best_practices_step_merge_vs_split:

When to merge versus split steps
=================================

.. image:: /_static/images/step_merge_vs_split.svg
   :align: center
   :width: 80%
   :alt: Side-by-side comparison showing when to merge steps into one versus splitting into multiple

Merge when:

- Simple workflow with few parameters.
- All inputs and outputs share the same context.
- A single user role handles the entire flow.

.. code-block:: python
   :caption: Merged — simple workflow with few fields

   class UnitConverterStep(StepModel):
       """Simple enough to keep in a single step."""

       value: float = 0.0
       from_unit: str = "mm"
       to_unit: str = "in"
       converted_value: float = 0.0

       @transaction(self=StepSpec(download=["value", "from_unit", "to_unit"], upload=["converted_value"]))
       def convert(self) -> None:
           conversion_factors = {"mm_to_in": 0.03937}
           key = f"{self.from_unit}_to_{self.to_unit}"
           self.converted_value = self.value * conversion_factors.get(key, 1.0)

Split when:

- Users need to inspect intermediate outputs.
- Different phases require different expertise (for example, an electrical engineer runs
  the electro-magnetic simulation, then a mechanical engineer runs the thermal simulation).
- Setup and results need different UI (for example, a page for CAD import and meshing, a
  page for solver configuration and results, and a page for post-processing and
  visualization).

.. code-block:: python
   :caption: Split — multi-physics workflow with separate concerns

   class ElectromagneticStep(StepModel):
       """EM simulation — owned by electrical engineer."""

       frequency: float = 1e9
       power_loss: float = 0.0

       @transaction(self=StepSpec(download=["frequency"], upload=["power_loss"]))
       def solve_em(self) -> None:
           self.power_loss = compute_em_losses(self.frequency)

   class ThermalStep(StepModel):
       """Thermal simulation — owned by mechanical engineer."""

       max_temperature: float = 0.0

       @transaction(
           self=StepSpec(upload=["max_temperature"]),
           electromagnetic=StepSpec(download=["power_loss"]),
       )
       def solve_thermal(self, electromagnetic: ElectromagneticStep) -> None:
           self.max_temperature = compute_thermal(electromagnetic.power_loss)
