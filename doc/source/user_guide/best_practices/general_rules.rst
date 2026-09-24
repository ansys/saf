.. _best_practices_general_rules:

#############
General rules
#############

This section covers the fundamental rules that apply to all SAF solution code.


No top-level executable code
============================

Modules must not contain executable code at the top level. Place all logic inside
functions, methods, or ``if __name__ == "__main__":`` guards.

When SAF GLOW Engine imports your step modules, any code at the module level executes
immediately. This causes side effects, slows startup, and can break the framework entirely.

.. code-block:: python
   :caption: Incorrect — top-level executable code

   # setup_step.py
   import numpy as np

   data = np.zeros(100)  # Runs on import — breaks GLOW
   result = expensive_function()  # Side effect on import


   class SetupStep(StepModel): ...

.. code-block:: python
   :caption: Correct — all logic inside class methods

   # setup_step.py
   from ansys.saf.glow.solution import StepModel, StepSpec, transaction


   class SetupStep(StepModel):
       """Setup step — no code runs on import."""

       data: list[float] = []
       result: float = 0.0

       @transaction(self=StepSpec(upload=["data", "result"]))
       def initialize(self) -> None:
           import numpy as np  # Heavy import inside the method

           self.data = np.zeros(100).tolist()
           self.result = expensive_function()


Test business logic in isolation first
=======================================

Validate your domain functions (solvers, transforms, PyAnsys calls) in standalone scripts
or unit tests before wiring them into SAF transactions. This catches algorithm bugs early,
without the overhead of the full framework.

.. image:: /_static/images/recommended_dev_flow.svg
   :align: center
   :width: 70%
   :alt: Diagram showing the recommended development flow: write domain logic, unit-test, wire into SAF, integration test

.. code-block:: python
   :caption: Example — testable domain function

   # logic/beam_solver.py
   def compute_deflection(length: float, load: float, modulus: float) -> float:
       """Compute beam deflection — pure function, no SAF dependency."""
       return (load * length**3) / (3 * modulus)

.. code-block:: python
   :caption: Example — unit test for the domain function

   # tests/test_beam_solver.py
   from logic.beam_solver import compute_deflection


   def test_compute_deflection():
       result = compute_deflection(length=1.0, load=100.0, modulus=200e9)
       assert result > 0

.. code-block:: python
   :caption: Example — wiring into a SAF transaction after validation

   from ansys.saf.glow.solution import StepModel, StepSpec, transaction
   from logic.beam_solver import compute_deflection


   class BeamStep(StepModel):
       """Beam analysis step."""

       length: float = 1.0
       load: float = 100.0
       modulus: float = 200e9
       deflection: float = 0.0

       @transaction(self=StepSpec(download=["length", "load", "modulus"], upload=["deflection"]))
       def solve(self) -> None:
           self.deflection = compute_deflection(self.length, self.load, self.modulus)


Backend-first development
==========================

Build and test all backend logic before writing any frontend code. This rule ensures a
stable API layer before you invest time in UI code that depends on it.

Run your solution with ``saf run`` and open the auto-generated API documentation at
``http://localhost:<port>/docs``. From there you can invoke any transaction directly,
inspect request/response payloads, and confirm that every method returns ``Completed``
before writing a single line of frontend code.

.. image:: /_static/images/backend_first_workflow.svg
   :align: center
   :width: 70%
   :alt: Diagram showing the two virtual environments created by saf install and the symbolic link between them
