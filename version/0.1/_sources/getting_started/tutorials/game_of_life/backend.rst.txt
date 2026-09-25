.. _game_of_life_backend:

Phase 3 — Backend
#################

.. topic:: Objective

 In this module, you'll cover the following topics:

  - :material-outlined:`add_box;1.25em;saf-objective-icon` Add a new step to the solution with
    ``saf add-step``.
  - :material-outlined:`account_tree;1.25em;saf-objective-icon` Declare the workflow contract in the
    **solution definition**.
  - :material-outlined:`data_object;1.25em;saf-objective-icon` Define the **step model** and its
    **typed fields** — where the state lives.
  - :material-outlined:`sync_alt;1.25em;saf-objective-icon` Write **transaction methods**, the only
    place where state is read and written.
  - :material-outlined:`rule;1.25em;saf-objective-icon` Declare **field dependencies**
    (``StepSpec``) so SAF knows what to load and save.
  - :material-outlined:`timer;1.25em;saf-objective-icon` Choose between **blocking** and
    **long-running** transactions — synchronous or background execution.
  - :material-outlined:`podcasts;1.25em;saf-objective-icon` Publish **events** to stream progress
    from the backend to the UI in real time.

  At the end of this phase, the ready-made engine from
  :ref:`phase 2 <game_of_life_business_logic>` is fully wired into a SAF backend.

.. tip::

    This page is where you meet the fundamentals of the framework. Each of them is called out
    in a purple **Key concept** box like the ones below — if you only read one thing per
    section, read those.

.. note::

    Every code snippet on this page is pulled directly from the
    `SAF examples solution <https://github.com/ansys/saf/tree/main/examples>`__, so what you
    read here is always in sync with code that is built and tested on every commit.

    One consequence: the import paths show the **examples** namespace. In your own solution,
    replace

    .. code-block:: text

        saf.solutions.examples.solution.game_of_life

    with

    .. code-block:: text

        saf.solutions.game_of_life.solution.game_of_life

Where you are heading
=====================

Here is the complete backend you will end up with. Skim it now, then come back to it whenever
a snippet below feels out of context.

.. dropdown:: Complete ``game_of_life_step.py``
    :icon: code

    .. literalinclude:: ../../../../../examples/src/saf/solutions/examples/solution/game_of_life_step.py
        :language: python
        :caption: solution/game_of_life_step.py
        :lines: 20-

Barely fifty lines — and yet it exercises every backend concept SAF has to offer. Now unpack
it, one concept at a time.

Add a new step
==============

The scaffold you created in :ref:`phase 1 <game_of_life_initialization>` ships with two example
steps — ``FirstStep`` and ``SecondStep``. You will replace them with a single new step called
``game_of_life_step``.

.. practice::

    From the root of the ``game-of-life`` folder, run:

    .. code-block:: bash

        saf add-step --step-name game_of_life_step --ui-framework dash

    The command prompts for a step template. Press :kbd:`Enter` to accept the default
    ``calculator-step``, which generates the sample "add two numbers" step you are about to
    replace.

    ``saf add-step`` creates **both** the backend and the frontend file for the new step at
    once:

    - ``src/saf/solutions/game_of_life/solution/game_of_life_step.py`` (backend).
    - ``src/saf/solutions/game_of_life/ui/pages/game_of_life_page.py`` (frontend).

    It also registers the step in ``definition.py``. You will keep the frontend file for
    :ref:`phase 4 <game_of_life_frontend>`; for now, focus on the backend one.

.. note::

    The page router in ``ui/pages/page.py`` needs no edit, ever. Pages advertise themselves
    through ``dash.register_page``, and the router builds the navigation tree from Dash's page
    registry. Adding or deleting a page file is enough.

The solution definition
=======================

.. key-concept:: Solution definition

    ``definition.py`` is the **single source of truth** of the workflow. A ``StepsModel``
    subclass lists every step as a typed attribute, and a ``Solution`` subclass ties the
    display name, the schema version and that step model together. The SAF runtime reads this
    file at startup to discover what the solution is made of.

Open ``src/saf/solutions/game_of_life/solution/definition.py``. This is the file the SAF
runtime reads to discover what steps exist and in what order they should be presented.

Right after ``saf add-step``, it looks something like this:

.. code-block:: python

    from ansys.saf.glow.solution import Solution, StepsModel

    from saf.solutions.game_of_life.solution.first_step import FirstStep
    from saf.solutions.game_of_life.solution.second_step import SecondStep
    from saf.solutions.game_of_life.solution.game_of_life_step import GameOfLifeStep


    class Steps(StepsModel):
        """Workflow definition."""

        first_step: FirstStep
        second_step: SecondStep
        game_of_life_step: GameOfLifeStep


    class GameOfLifeSolution(Solution):
        """Solution definition."""

        display_name: str = "Game of Life"
        version: int = 1
        steps: Steps

Three things are worth pointing out:

- ``Steps`` inherits from ``StepsModel`` and lists every step as a typed attribute. The
  attribute name (``game_of_life_step``) is how you will reach the step from the frontend later
  on: ``project.steps.game_of_life_step``.
- ``GameOfLifeSolution`` inherits from ``Solution`` and ties the display name, a schema
  version, and the ``Steps`` model together. This is the entrypoint the SAF runtime picks up
  when it boots the app.
- The imports at the top of the file are what the SAF runtime uses to *discover* the step
  classes. Removing a step from the definition without removing its import would leave dead
  code around, so always keep the two in sync.

.. practice::

    You only need one step for this tutorial, so delete the leftover ``FirstStep`` and
    ``SecondStep``:

    #. Delete the files ``solution/first_step.py`` and ``solution/second_step.py``.
    #. Delete the files ``ui/pages/first_page.py`` and ``ui/pages/second_page.py``.
    #. Remove or rewrite the generated ``tests/unit/test_solution_api.py`` and
       ``tests/unit/test_solution_ui.py`` because they still exercise the deleted
       calculator step and page.
    #. Edit ``solution/definition.py`` to look exactly like this:

       .. code-block:: python

           from ansys.saf.glow.solution import Solution, StepsModel

           from saf.solutions.game_of_life.solution.game_of_life_step import GameOfLifeStep


           class Steps(StepsModel):
               """Workflow definition."""

               game_of_life_step: GameOfLifeStep


           class GameOfLifeSolution(Solution):
               """Solution definition."""

               display_name: str = "Game of Life"
               version: int = 1
               steps: Steps

    Save all the files. There is nothing to change in ``ui/pages/page.py``: deleting the two
    page files is enough for them to disappear from the navigation tree.

The step model
==============

.. key-concept:: Step model

    A **step** is one unit of the workflow, described by a class that inherits from
    ``StepModel``. It owns two things, and only two things:

    - **fields**: the typed, persistent state of the step;
    - **transaction methods**: the place where the business logic is called and the fields are read and written.

Open the freshly generated ``solution/game_of_life_step.py``. The scaffold gives you a toy
adder:

.. code-block:: python

    from ansys.saf.glow.solution import StepModel, StepSpec, transaction


    class GameOfLifeStep(StepModel):
        """Step definition of the game_of_life_step step."""

        first_arg: float = 0
        second_arg: float = 0
        result: float = 0

        @transaction(
            self=StepSpec(upload=["result"], download=["first_arg", "second_arg"]),
        )
        def calculate(self) -> None:
            """Compute the sum of two numbers."""
            self.result = self.first_arg + self.second_arg

That is the shape of every SAF step. You are going to replace the whole body.

Typed fields
------------

.. key-concept:: Typed field

    A field is nothing more than a class attribute with a **type annotation** and a **default
    value**. SAF uses those annotations to:

    - persist the field to storage between transactions;
    - expose it in the auto-generated REST API;
    - surface it to the frontend through the ``DashClient``.

.. warning::

    **Every** field must carry a type annotation. Untyped attributes lead to data validation errors at runtime.

For the Game of Life, three inputs and two outputs are enough:

.. literalinclude:: ../../../../../examples/src/saf/solutions/examples/solution/game_of_life_step.py
    :language: python
    :caption: solution/game_of_life_step.py
    :start-at: class GameOfLifeStep
    :end-before: @transaction

The first three fields are **inputs**: the user drives them from the UI. The last two are
**outputs**: they are filled in by the transaction methods.

.. warning::

    Field values must be **JSON-serializable**, because they travel over the REST API between
    the backend and the frontend. That is why ``initial_grid_state`` and ``grid_states`` are
    plain nested ``list`` of ``int`` rather than NumPy arrays — and why the transactions call
    ``.tolist()`` before assigning a grid to a field.

The imports the step needs are equally short — the SAF primitives on one side, your own
business logic on the other:

.. literalinclude:: ../../../../../examples/src/saf/solutions/examples/solution/game_of_life_step.py
    :language: python
    :caption: solution/game_of_life_step.py
    :start-at: from ansys.saf.glow.solution
    :end-before: class GameOfLifeStep

.. practice::

    In ``game_of_life_step.py``, replace the scaffold imports and the body of
    ``GameOfLifeStep`` with the two snippets above. Delete the ``calculate`` method and the
    ``first_arg``, ``second_arg`` and ``result`` fields — you don't need them.

    | Remember to point the ``SimulationController`` import at **your** business logic module:
    | ``from saf.solutions.game_of_life.solution.game_of_life import SimulationController``.

Transaction methods
===================

.. key-concept:: Transaction method

    Fields are inert data. **Transaction methods** are what make a step do something. In
    SAF they are the place where the business logic is called and the fields are read and written.
    Any method that touches a field must be decorated with ``@transaction``.

    Every transaction comes in one of two flavors:

    - **Blocking** (the default): The caller waits until the method returns. Use it for fast,
      deterministic work.
    - **Long-running** (``@long_running``): The call returns immediately and the method keeps
      going in the background. Use it for anything slow or iterative.

Blocking or long-running?
-------------------------

The two flavors are not interchangeable: the choice is driven by **how long the work takes**
and by **what the user should be able to do while it runs**.

.. list-table::
   :header-rows: 1
   :stub-columns: 1
   :widths: 20 35 45

   * -
     - Blocking transaction
     - Long-running transaction (``@long_running``)
   * - Declaration
     - ``@transaction(...)``
     - ``@transaction(...)`` + ``@long_running``
   * - Caller behavior
     - Waits for the method to return
     - Returns immediately, work continues in the background
   * - Typical duration
     - Milliseconds to a couple of seconds
     - Seconds, minutes, hours
   * - UI during execution
     - Frozen — the user can do nothing else
     - Responsive — the user can navigate, cancel, watch progress
   * - Progress reporting
     - None: the result appears all at once
     - ``raise_event`` streams intermediate results in real time
   * - Monitoring and control
     - Not applicable
     - ``get_method_state()``, cancellation, termination event
   * - Typical use cases
     - Validating inputs, preparing a preview, formatting results,
       reading a small file
     - Running a solver, meshing, launching a PyAnsys session,
       iterative loops, batch post-processing

.. tip::

    **Rule of thumb**: If the user would notice a spinner, make it long-running. A blocking
    transaction that takes more than a second or two makes the whole application feel broken,
    and one that takes minutes will hit client-side timeouts.

    Conversely, do not make everything long-running. The background machinery adds latency and forces the frontend to handle events and completion, which is needless complexity for a computation that takes
    10 ms.

In this step, you will write one of each: ``display_initial_state`` is blocking, and
``simulate`` — covered in the :ref:`next section <game_of_life_backend_long_running>` — is
long-running.

Writing a blocking transaction
------------------------------

The user picks a pattern in the UI and immediately wants to see it drawn on the grid. That is
a tiny, instantaneous computation, so a plain **blocking** transaction is the right tool:

.. literalinclude:: ../../../../../examples/src/saf/solutions/examples/solution/game_of_life_step.py
    :language: python
    :caption: solution/game_of_life_step.py
    :pyobject: GameOfLifeStep.display_initial_state

Three lines of business logic, wrapped in a decorator. Look at that decorator closely — it
carries two new concepts.

The ``@transaction`` decorator
------------------------------

.. key-concept:: ``@transaction``

    The decorator does three important things behind the scenes:

    - It runs the method in an **isolated execution context**, so it behaves identically on
      your laptop, in a Docker container, or on an on-prem cluster.
    - It publishes the method as a **POST endpoint in the auto-generated REST API**. You will
      call it from the Dash frontend in phase 4, but you could just as well call it with
      ``curl``.
    - It records **which fields the method reads and which it writes**, so the SAF runtime
      knows what to load before the call and what to persist after it.

That last point is what the ``StepSpec`` argument is for.

Field dependencies with ``StepSpec``
------------------------------------

.. key-concept:: ``StepSpec``

    ``StepSpec`` declares the field dependencies of a transaction: ``download`` lists the
    fields loaded from storage **before** the method runs, and ``upload`` lists the fields
    persisted **after** it finishes. A field that is not declared either holds no meaningful
    value on entry, or is silently dropped on exit.

In ``display_initial_state``, that declaration reads:

.. code-block:: python

    self=StepSpec(
        upload=["initial_grid_state"],
        download=["selected_pattern", "grid_size"],
    )

Read it like this:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Argument
     - Meaning
   * - ``download``
     - Fields the transaction **reads** from persistent storage *before* running. The method's
       *inputs*. Only these fields are guaranteed to hold a meaningful value inside the body.
   * - ``upload``
     - Fields the transaction **writes back** to persistent storage *after* it finishes. The
       method's *outputs*. Fields you assign but forget to declare are silently dropped.

.. tip::

    **Rule of thumb**: if a field appears on the left-hand side of an assignment inside the
    transaction, it belongs in ``upload``. If it appears on the right-hand side, it belongs in
    ``download``. Forgetting either is the number-one gotcha for new SAF developers.

Why declare this explicitly instead of letting SAF figure it out? Because ``download`` /
``upload`` is precisely what lets a solution be split across process, container and machine
boundaries without you writing a single line of serialization code. The step model becomes a
contract that the runtime can honor anywhere.

.. note::

    The keyword is ``self=`` because a transaction may depend on **several** steps, not just
    its own. A step can declare ``other_step=StepSpec(download=[...])`` to read fields produced
    upstream — that is how a multi-step workflow chains data together.

.. practice::

    Add the ``display_initial_state`` transaction to ``game_of_life_step.py``.

    You now have a fully working blocking transaction. It is already testable through the
    auto-generated REST API — try it later with ``saf run --no-ui`` if you are curious.

.. _game_of_life_backend_long_running:

Long-running transactions
=========================

The simulation itself is a different beast: it is an **iterative loop** that can run for
seconds or minutes depending on the grid size and the iteration count. It lands squarely in
the right-hand column of the comparison table above. Blocking the UI for that long is not
acceptable — and the user would much rather *watch the grid evolve* than stare at a spinner
until the final result arrives.

Two more SAF features cover exactly this:

- the ``@long_running`` decorator, which turns the transaction into a **non-blocking
  background job**;
- ``self.transaction.raise_event(...)``, which **streams events** from the running method back
  to any interested listener.

Here is the resulting transaction:

.. literalinclude:: ../../../../../examples/src/saf/solutions/examples/solution/game_of_life_step.py
    :language: python
    :caption: solution/game_of_life_step.py
    :pyobject: GameOfLifeStep.simulate

The ``@long_running`` decorator
-------------------------------

.. key-concept:: ``@long_running``

    Stacking ``@long_running`` **under** ``@transaction`` turns the method into a non-blocking
    background job:

    - The call returns **immediately** on the client side. The transaction starts
      asynchronously and the SAF runtime tracks its state.
    - The client can poll the method status through ``step.get_method_state("simulate")``,
      or listen for the termination event.

.. warning::

    **Decorator order matters.** ``@long_running`` sits immediately above the method and
    **below** ``@transaction``:

    .. code-block:: python

        @transaction(...)
        @long_running
        def simulate(self) -> None:
            ...

    Swap the two and the runtime cannot see the long-running semantics.

Also notice the ``download`` set: ``simulate`` needs the same inputs the user tuned before
launching the run (``selected_pattern``, ``grid_size``) **plus** one that
``display_initial_state`` does not care about — ``max_iterations``. Each transaction declares
only what it truly needs, nothing more.

Events
======

A long-running job that says nothing until it is done is barely better than a blocking one.

.. key-concept:: Event

    **Events** are how a SAF backend talks to the outside world *while it is still running*.
    Inside a transaction, ``self.transaction.raise_event(message=..., stream_name=...)``
    publishes a JSON-serializable message on a named stream that any listener — typically the
    frontend — can subscribe to in real time.

Every call to ``raise_event`` looks like this:

.. code-block:: python

    self.transaction.raise_event(
        message={"grid": state.grid.tolist(), "iteration": iterations},
        stream_name="my-stream",
    )

- ``message`` is any **JSON-serializable** dict. Here, one full grid plus the generation
  number.
- ``stream_name`` is a free-form identifier that you choose. The frontend subscribes to it by
  name in :ref:`phase 4 <game_of_life_frontend>`.

Multiple streams can coexist. A common pattern in real solutions is one stream per kind of
update — progress, warnings, intermediate artifacts.

.. note::

    Events are *transient*: they are delivered to whoever is listening at that moment and are
    not replayed. That is why ``simulate`` **also** appends every grid to the ``grid_states``
    field. The events drive the live animation; the field is the durable record that survives
    a page reload.

Termination events
------------------

.. key-concept:: Termination event

    Passing ``enable_termination_event=True`` to ``@transaction`` asks SAF to emit an event on
    a stream **named after the method** whenever it terminates — whether it succeeded, failed,
    or was cancelled.

Both transactions of the step enable it, so the ``simulate`` method produces two kinds of
events:

.. list-table::
   :header-rows: 1
   :stub-columns: 1
   :widths: 20 25 55

   * - Stream
     - Emitted by
     - Used by the frontend to...
   * - ``my-stream``
     - Your explicit ``raise_event`` calls
     - Redraw the heatmap after every generation
   * - ``simulate``
     - ``enable_termination_event=True``
     - Re-enable the "Start simulation" button and show a notification

.. practice::

    Add the ``simulate`` transaction to ``game_of_life_step.py``. Your file should now match
    the complete listing at the top of this page — take a moment to diff yours against it.

The mental model
================

At this point ``GameOfLifeStep`` embodies the whole backend and it demonstrates every SAF
building block you will ever need:

.. mermaid::

    flowchart LR
        subgraph Frontend
            UI[Dash page]
        end

        subgraph Backend[SAF backend]
            direction TB
            F1[grid_size, selected_pattern, max_iterations]
            F2[initial_grid_state]
            F3[grid_states]
            T1["display_initial_state()<br/>(blocking)"]
            T2["simulate()<br/>(long_running)"]
        end

        UI -- sets fields --> F1
        F1 -- download --> T1
        F1 -- download --> T2
        T1 -- upload --> F2
        T2 -- upload --> F3
        F2 -- read via DashClient --> UI
        T2 -- raise_event --> UI

- **Fields** hold state. They are typed and persistent.
- **Transactions** are the place where the business logic is called and the fields are read and written.
  ``download`` / ``upload`` dependencies through ``StepSpec``.
- **Blocking transactions** return only after the work is done.
- **Long-running transactions** return immediately and use **events** to stream progress and
  a **termination event** to signal completion.

Key takeaways
=============

.. important::

    - The **solution definition** lists the workflow steps in a ``StepsModel`` and ties them
      together with the ``Solution`` class.
    - A **step model** is a ``StepModel`` subclass whose typed class attributes are its
      **fields**. Every field needs a type annotation — no exceptions.
    - **Field values must be JSON-serializable**. Convert NumPy arrays with ``.tolist()``
      before storing them in a field.
    - Any method that touches fields is decorated with ``@transaction`` and declares its
      **field dependencies** in a ``StepSpec`` (``download`` for reads, ``upload`` for writes).
    - Stack ``@long_running`` **under** ``@transaction`` to turn a method into a background
      job that returns immediately.
    - Emit real-time updates from a long-running method with
      ``self.transaction.raise_event(message=..., stream_name=...)``.
    - Set ``enable_termination_event=True`` on a transaction to get an automatic event on the
      stream named after the method when it finishes (success, failure or cancellation).