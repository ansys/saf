.. _game_of_life_frontend:

Phase 4 — Frontend
##################

.. topic:: Objective

  In this module, you'll cover the following topics:

  - :material-outlined:`folder_open;1.25em;saf-objective-icon` Discover where frontend code lives
    in a SAF solution, and the anatomy of a SAF Dash page.
  - :material-outlined:`link;1.25em;saf-objective-icon` Register the page and give it a **typed
    handle** on the solution through ``dash.register_page``.
  - :material-outlined:`dashboard;1.25em;saf-objective-icon` Build the **layout** function that
    turns step fields into interactive Dash and Mantine controls.
  - :material-outlined:`bolt;1.25em;saf-objective-icon` Write **callbacks** that read and write
    fields and invoke transactions through the ``DashClient`` — no manual HTTP calls.
  - :material-outlined:`hearing;1.25em;saf-objective-icon` Hook **event listeners** to the streams
    your long-running transaction publishes, and animate the UI in real time.
  - :material-outlined:`play_circle;1.25em;saf-objective-icon` Run the finished solution with
    ``saf run --debug`` and watch the Game of Life evolve.

  At the end of this phase, the backend from :ref:`phase 3 <game_of_life_backend>` is driven by
  a fully interactive Dash page.

SAF is deliberately frontend-agnostic. The same backend could be driven from Streamlit,
from a custom React app, or from a plain HTTP client. This tutorial uses
`Plotly Dash <https://dash.plotly.com/>`_.

This phase explains the Dash concepts only as far as you need them to wire the SAF backend.
Every one of them is covered in depth in the official documentation, and each section below
links to the matching page. If Dash is new to you, start with the
`Dash fundamentals <https://dash.plotly.com/layout>`__ and come back here.


Where the frontend lives
========================

All frontend code lives under ``src/saf/solutions/game_of_life/ui/``:

.. code-block:: text

    ui/
    ├── app.py                # DashProxy app instance (auto-generated, don't touch)
    ├── assets/               # CSS, icons, images
    ├── components/           # Reusable Dash components
    └── pages/
        ├── about_page.py     # Landing page (auto-generated)
        ├── game_of_life_page.py   # ← the file you will edit
        └── page.py           # Page router (auto-generated, don't touch)

You already have a ``game_of_life_page.py`` skeleton from ``saf add-step``. You are going to
replace its body with a fully functional page.

The full frontend
=================

Here is the file you are aiming at. Expand the dropdown to skim it now; the rest of the phase dissects it one block
at a time.

.. dropdown:: Complete ``game_of_life_page.py``
    :icon: code

    .. literalinclude:: ../../../../../examples/src/saf/solutions/examples/ui/pages/game_of_life_page.py
        :language: python
        :caption: ui/pages/game_of_life_page.py
        :lines: 20-

.. note::

    As in phase 3, the snippets on this page are pulled straight from the
    `SAF examples solution <https://github.com/ansys/saf/tree/main/examples>`__. Wherever you
    see ``saf.solutions.examples`` or ``ExamplesSolution``, substitute
    ``saf.solutions.game_of_life`` and ``GameOfLifeSolution``.

Anatomy of a SAF Dash page
==========================

.. key-concept:: SAF Dash page

    Every SAF Dash page, no matter how complex, is built from the same three blocks:

    #. **Imports and page registration**: declare the URL under which the page is reachable.
    #. **The ``layout`` function**: receives a ``project`` (an instance of your ``Solution``
       class) and returns a Dash component tree. This is where you build the visual.
    #. **Callbacks**: decorated functions that fire in response to UI events (click, change,
       …) or backend events (streams).

    Recognizing those three blocks is enough to find your way around any SAF page, including
    ones you did not write.

The rest of this phase walks through the three blocks in order.

Page registration
=================

.. key-concept:: Page registration

    ``dash.register_page`` declares the URL of the page, its label in the navigation tree and
    its icon. Its ``path_template`` **must** contain ``<project_id>``, because every piece of
    state in SAF is scoped to a project: that placeholder is what lets the runtime resolve
    which project's data the page works on.

    See `Multi-page apps and URL support <https://dash.plotly.com/urls>`__ in the Dash
    documentation, and in particular the
    `variable paths <https://dash.plotly.com/urls#variable-paths>`__ section, which explains
    the ``<variable_name>`` syntax SAF relies on.

.. literalinclude:: ../../../../../examples/src/saf/solutions/examples/ui/pages/game_of_life_page.py
    :language: python
    :caption: ui/pages/game_of_life_page.py
    :start-at: dash.register_page
    :end-before: def layout

Two things to note:

- ``name`` is the label shown in the navigation tree; ``icon_asset_name`` and
  ``icon_asset_path`` point at an SVG under ``ui/assets/`` and are optional.
- ``path_template`` is what makes the page addressable: the runtime substitutes the real
  project identifier when the user navigates to it.

The imports at the top of the file follow the same split you saw in the backend — SAF
primitives, Dash/Plotly components, and finally your own solution:

.. literalinclude:: ../../../../../examples/src/saf/solutions/examples/ui/pages/game_of_life_page.py
    :language: python
    :caption: ui/pages/game_of_life_page.py
    :start-at: import json
    :end-before: logger =

Importing your ``Solution`` class from ``definition.py`` gives every callback a **typed handle**
on the whole solution — you get IDE completion on ``project.steps.game_of_life_step`` and its
fields, for free.

The layout function
===================

.. key-concept:: ``layout(project)``

    The **layout** function is the entry point of the page. Its signature is fixed: SAF calls
    it with the ``Solution`` instance matching the ``<project_id>`` in the URL, and expects a
    Dash component tree in return.

    Annotating the parameter with your own ``Solution`` class turns ``project`` into a
    **typed handle** on the whole workflow: ``project.steps.game_of_life_step`` and its fields
    come with full IDE completion. Reading a field inside the layout is how you seed a control
    with a value already stored in the backend.

    See `Dash layout <https://dash.plotly.com/layout>`__ for the general principles, and
    `layout in Dash pages <https://dash.plotly.com/urls#layout>`__ for the function form used
    here.

The signature of the layout is fixed: SAF calls it with the project matching the
``<project_id>`` in the URL.

.. code-block:: python

    def layout(project: GameOfLifeSolution) -> html.Div:
        step = project.steps.game_of_life_step
        return html.Div([...])

From there, you dereference the step you care about and use its fields as **initial values**
for the controls.

The layout of this page is a two-column grid:

- **Left column (3/12)** — the controls: a pattern picker, a max-iterations input, a grid-size
  slider, a :guilabel:`Start simulation` button, and a small status area (iteration counter + progress
  bar).
- **Right column (9/12)** — a Plotly ``Heatmap`` figure driven by the grid data.

.. dropdown:: The full ``layout`` function
    :icon: code

    .. literalinclude:: ../../../../../examples/src/saf/solutions/examples/ui/pages/game_of_life_page.py
        :language: python
        :caption: ui/pages/game_of_life_page.py
        :pyobject: layout

Most of it is plain Dash and Mantine markup, documented outside SAF:

- `Dash HTML components <https://dash.plotly.com/dash-html-components>`__ for ``html.Div`` and
  friends — one class per HTML tag.
- `Dash core components <https://dash.plotly.com/dash-core-components>`__ for ``dcc.Graph``,
  ``dcc.Store`` and the other interactive building blocks.
- `Dash Mantine Components <https://www.dash-mantine-components.com/>`__ for the grid, the
  dropdown, the slider and the buttons used in this page.
- `Plotly heatmaps <https://plotly.com/python/heatmaps/>`__ for the figure that renders the
  grid of cells.

The two SAF-specific lines are right at the end:

.. code-block:: python

    DashClient.create_event_listener(step, stream_name="my-stream", id="update-heatmap"),
    DashClient.create_event_listener(step, stream_name="simulate", id="termination"),

.. key-concept:: Event listener

    ``DashClient.create_event_listener(step, stream_name=..., id=...)`` is the frontend
    counterpart of the backend's ``raise_event``. It inserts an **invisible component** in the
    layout that subscribes to a named backend stream and updates its ``message`` property
    every time an event arrives.

    The ``id`` you give it is what a callback targets with ``Input("<id>", "message")``. One
    listener per stream: here, one for the progress stream and one for the termination stream.

.. practice::

    #. Replace the whole content of ``game_of_life_page.py`` with the complete listing above
       — imports, ``dash.register_page`` and ``layout``. Remember to substitute the
       ``saf.solutions.examples`` namespace and ``ExamplesSolution`` with your own.

    #. The "Start Simulation" button uses an icon that the template does not ship. Download
       `mdi--play.svg <https://github.com/ansys/saf/blob/main/examples/src/saf/solutions/examples/ui/assets/icons/mdi--play.svg>`__
       and drop it into ``src/saf/solutions/game_of_life/ui/assets/icons/``. Without it the
       button renders with a broken image.

    Save the file and continue — the page is not usable until the callbacks are in place.

Callbacks 101
=============

.. key-concept:: Callback

    A **callback** is a function decorated with ``@callback`` that reacts to changes in the
    application. It is described by three kinds of arguments:

    - ``Input``: a value SAF **watches**. When it changes, the callback fires.
    - ``State``: a value SAF **reads but does not watch**.
    - ``Output``: a value SAF **writes back** to the browser once the callback returns.

    Callbacks are where the frontend drives the backend — which makes them the frontend
    mirror of the backend's transaction methods.

    See `Basic callbacks <https://dash.plotly.com/basic-callbacks>`__ for ``Input`` and
    ``Output``, `Dash app with state <https://dash.plotly.com/basic-callbacks#dash-app-with-state>`__
    for ``State``, and `Advanced callbacks <https://dash.plotly.com/advanced-callbacks>`__ for
    everything beyond the basics.

A callback in Dash is a decorated function that reacts to changes in the UI:

.. code-block:: python

    @callback(
        Output("some-component-id", "some-property"),
        Input("triggering-component-id", "triggering-property"),
        State("read-only-component-id", "read-only-property"),
    )
    def my_callback(triggering_value, read_only_value):
        ...
        return new_value_for_the_output

Two rules to internalize:

1. The number of ``Input`` + ``State`` arguments in the decorator must match the number of
   function parameters. SAF passes you an extra ``project`` parameter automatically when the
   last ``State`` is ``State("url", "pathname")``.
2. The number of ``Output`` entries in the decorator must match the number of items in the
   ``return`` statement.

.. tip::

    The mental model between a SAF backend ``@transaction`` and a Dash ``@callback`` is
    intentionally similar:

    ============================== ==================================
    SAF ``@transaction``           Dash ``@callback``
    ============================== ==================================
    ``StepSpec(download=[...])``   ``Input(...)`` and ``State(...)``
    ``StepSpec(upload=[...])``     ``Output(...)``
    ============================== ==================================

Callback #1 — Preview the initial pattern
=========================================

.. key-concept:: ``DashClient``

    The ``DashClient`` is the bridge between the Dash page and the SAF backend. Through the
    typed ``project`` handle it exposes the step model as if it were a local object:

    - **assigning** to a field (``step.grid_size = 20``) persists it in the backend;
    - **reading** a field (``step.initial_grid_state``) fetches its current value;
    - **calling** a transaction (``step.display_initial_state()``) executes it.

    There is no ``requests.post`` anywhere in a SAF page; the client turns each of those
    Pythonic operations into the corresponding REST API call under the hood.

Whenever the user picks a new pattern or moves the grid-size slider, you want the heatmap to
redraw immediately. There is no long computation involved — the blocking
``display_initial_state`` transaction is perfect for the job.

.. literalinclude:: ../../../../../examples/src/saf/solutions/examples/ui/pages/game_of_life_page.py
    :language: python
    :caption: ui/pages/game_of_life_page.py
    :pyobject: update_initial_pattern

Notice the flow:

1. Access the step through ``project.steps.game_of_life_step``.
2. **Write** the two input fields (``selected_pattern``, ``grid_size``) — SAF persists them.
3. **Invoke** the transaction. Because it is blocking, execution pauses until it returns.
4. **Read** the output field (``initial_grid_state``) and use it to patch the figure.

The interaction with the backend is entirely Pythonic. There is no ``requests.post`` call
anywhere; SAF turns the field assignments and the ``display_initial_state()`` call into REST
API calls under the hood.

.. tip::

    ``dash.Patch`` returns a lightweight diff instead of a full figure. It keeps the payload
    small when only one property changes. See
    `Partial property updates <https://dash.plotly.com/partial-properties>`__ for the full list
    of operations a ``Patch`` supports.

Callback #2 — Launch the long-running simulation
=================================================

.. key-concept:: Calling a long-running transaction

    Calling a ``@long_running`` transaction from a callback **returns immediately**: the
    callback must not — and cannot — wait for the result. Its only job is to *fire and forget*
    the transaction and to put the UI in its "running" state, typically by disabling the
    controls that would start a second run.

    Everything that happens afterwards is driven by events, in separate callbacks.

Clicking "Start simulation" must launch the long-running ``simulate`` transaction and disable
the controls until it terminates. Because ``simulate`` is decorated with ``@long_running``, the
call returns immediately — you do **not** wait for the loop to finish here.

.. literalinclude:: ../../../../../examples/src/saf/solutions/examples/ui/pages/game_of_life_page.py
    :language: python
    :caption: ui/pages/game_of_life_page.py
    :pyobject: start_simulation

Two subtleties:

- ``prevent_initial_call=True`` prevents the callback from firing when the page first loads —
  otherwise it would start a simulation nobody asked for. See
  `Prevent callbacks from being executed on initial load <https://dash.plotly.com/advanced-callbacks>`__.
- Because ``step.simulate()`` is asynchronous, the callback exits after triggering it. All the
  live updates happen in the next two callbacks.

Callback #3 — React to progress events
======================================

.. key-concept:: Consuming an event

    An event listener is just another callback ``Input``: ``Input("<listener-id>",
    "message")``. The payload published by the backend arrives as a **JSON string** in
    ``message["data"]``, so decode it with ``json.loads`` before use.

    The callback fires **once per event**, so keep its body cheap.

Every time the backend calls ``self.transaction.raise_event(stream_name="my-stream", ...)``,
the event listener you declared in the layout fires. You wire a callback to it exactly like
you would with any UI event:

.. literalinclude:: ../../../../../examples/src/saf/solutions/examples/ui/pages/game_of_life_page.py
    :language: python
    :caption: ui/pages/game_of_life_page.py
    :pyobject: update_graph

The ``Input("update-heatmap", "message")`` matches the ``id="update-heatmap"`` on the event
listener component you created in the layout.

.. tip::

    This callback fires **once per event**. On a grid of 20 x 20 cells running for 10
    iterations, that means 11 callbacks: one for generation 0 (emitted before the loop) and
    one for each of the 10 iterations. Keep the callback body inexpensive.

Callback #4 — React to the termination event
=============================================

.. key-concept:: ``get_method_state()``

    A termination event tells you that a long-running transaction is **over**, but not how it
    ended. ``step.get_method_state("simulate").status`` gives you the terminal status:
    ``Completed`` on success or ``Failed`` if the transaction raises. Use it to restore the
    UI and show the corresponding notification.

The last callback listens to the ``simulate`` stream — the one automatically emitted because
you set ``enable_termination_event=True`` on the transaction. When it fires, the simulation
is over (either successfully or not) and it is time to re-enable the controls.

.. literalinclude:: ../../../../../examples/src/saf/solutions/examples/ui/pages/game_of_life_page.py
    :language: python
    :caption: ui/pages/game_of_life_page.py
    :pyobject: enable_new_simulation

Notice how ``step.get_method_state("simulate").status`` gives you the terminal status of the
transaction: ``Completed`` on success, ``Failed`` if it raised, or ``Terminated`` if it was
cancelled. Use it to show the right notification to the user.

The end-to-end flow
===================

.. mermaid::

    sequenceDiagram
        participant U as User
        participant D as Dash callbacks
        participant B as SAF backend
        participant L as Event listeners

        U->>D: Selects pattern
        D->>B: display_initial_state()  (blocking)
        B-->>D: initial_grid_state
        D-->>U: Heatmap updated

        U->>D: Clicks "Start simulation"
        D->>B: simulate()  (long_running, returns immediately)
        D-->>U: Buttons disabled + "Started" notification

        loop for each generation
            B->>L: raise_event(stream="my-stream")
            L->>D: update_graph callback
            D-->>U: Heatmap + counter update
        end

        B->>L: termination event (stream="simulate")
        L->>D: enable_new_simulation callback
        D-->>U: Buttons re-enabled + "Completed" notification

Run the solution
================

You now have a complete SAF solution. Time to see it in action.

.. practice::

    From the root of the ``game-of-life`` folder, run:

    .. code-block:: bash

        saf run --debug

    A desktop window opens. Click **Game of Life** in the navigation tree on the left.

    - Pick different patterns from the dropdown. The heatmap updates instantly (that is
      ``display_initial_state`` firing).
    - Drag the grid-size slider. Same behavior.
    - Click **Start simulation**. The controls grey out, a green notification pops up, and
      the heatmap animates generation by generation until it reaches ``max_iterations`` or
      every cell dies.
    - Wait for the run to complete. A completion notification appears and the controls
      re-enable.

    If something goes wrong, you have two places to look: the terminal, where SAF prints
    tracebacks from failing transactions, and the Dash error overlay in the corner of the page,
    which ``--debug`` enables to report callback errors in the UI itself. That overlay is part
    of `Dash dev tools <https://dash.plotly.com/devtools>`__, which also gives you a
    `callback graph <https://dash.plotly.com/devtools#callback-graph>`__ showing the order and
    duration of every callback. Common issues:

    - Missing field in ``upload``. The UI reads an empty ``initial_grid_state``.
    - Missing field in ``download``. The transaction sees a stale value.
    - Wrong decorator order (``@long_running`` above ``@transaction``). The method runs
      synchronously and blocks the UI.
    - Missing ``Input`` or ``State`` in a ``@callback``. The number of dependencies in the
      decorator no longer matches the number of function parameters, and Dash raises a
      mismatched-arguments error.
    - Missing ``Output``, or a ``return`` statement that does not return as many values as
      there are ``Output`` entries.
    - Unknown component identifier. An ``Input``, ``State`` or ``Output`` that points at an
      ``id`` absent from the layout — including the event listener ids ``update-heatmap`` and
      ``termination`` — makes the callback silently never fire.
    - Typos in field, property or ``id`` names. ``step.grid_sizes`` instead of
      ``step.grid_size``, or ``"value"`` instead of ``"checked"``, fail at runtime only.
    - Syntax errors in the page module. The page fails to import and disappears from the
      navigation tree altogether.

Key takeaways
=============

.. important::

    - The frontend interacts with the backend **through the** ``DashClient``. Assign to a field and it is persisted.
      Call a transaction method and it runs.
    - Callbacks and transactions mirror each other: ``Input``/``State`` matches ``download``,
      ``Output`` matches ``upload``.
    - Backend events are delivered to the frontend through
      ``DashClient.create_event_listener(step, stream_name=..., id=...)`` components declared
      in the layout, and consumed with a regular ``@callback(Input("<id>", "message"))``.
    - The ``enable_termination_event=True`` flag on a ``@transaction`` gives you a "method
      finished" event on a stream named after the method. Perfect for re-enabling UI
      controls after a long-running run.
    - Use ``dash.Patch()`` to send only the diff of a figure or component tree back to the
      browser; it keeps the update payload small.
    - Type hints on layout arguments (``project: GameOfLifeSolution``) unlock IDE completion
      on step fields — a small effort with a big payoff.