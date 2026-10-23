.. _game_of_life_tutorial:

###############
Game of Life
###############

.. topic:: Objective

    Build a complete, end-to-end SAF solution around Conway's Game of Life. From the pure Python
    business logic, through the SAF backend, up to an interactive Dash frontend, and finally a
    distributable desktop installer. Along the way, discover every SAF concept a solution
    developer needs to know.

Why the Game of Life?
=====================

Conway's `Game of Life <https://en.wikipedia.org/wiki/Conway%27s_Game_of_Life>`_ is a cellular
automaton on a 2D grid where each cell is either alive or dead. The next generation of the grid
is computed from three deceptively simple rules:

1. A live cell with **2 or 3 live neighbors** survives.
2. A dead cell with **exactly 3 live neighbors** becomes alive.
3. Any other cell dies (or stays dead).

That's it. Yet these rules are enough to reveal blinking oscillators, spaceships gliding across
the grid and self-replicating structures.

For a SAF tutorial the Game of Life has one big advantage: it stays product-agnostic while
exercising **most of** the building blocks that a real engineering solution needs.

SAF concepts you will meet
==========================

By the end of the tutorial you will have written and understood:

.. grid:: 1 2 2 2
  :gutter: 3
  :class-container: concept-cards

  .. grid-item-card:: :material-outlined:`account_tree;1.4em;saf-concept-icon` Solution definition - The shape of your app
    :class-card: concept-card

    The steps that make up your application.

    See :ref:`solution_definition`.

  .. grid-item-card:: :material-outlined:`dataset;1.4em;saf-concept-icon` Step model - Where each step stores its data and triggers computations
    :class-card: concept-card

    A step holds the inputs, outputs, and methods that make up a computation. It is the main building block of a SAF solution.

    See :ref:`step_models`.

  .. grid-item-card:: :material-outlined:`swap_vert;1.4em;saf-concept-icon` Fields - Inputs, Outputs and intermediate data
    :class-card: concept-card

    Data containers that hold the inputs, outputs, and intermediate data of a step. Fields can be typed, validated, and have dependencies on other fields.

    See :ref:`field_states`.

  .. grid-item-card:: :material-outlined:`bolt;1.4em;saf-concept-icon` Blocking transaction methods - Quick actions
    :class-card: concept-card

    Short computations that finish right away. For example, updating a field or very short calculations that return a result immediately.

    See :ref:`transaction_method_definition`.

  .. grid-item-card:: :material-outlined:`hourglass_top;1.4em;saf-concept-icon` Non-blocking transaction methods - Background jobs
    :class-card: concept-card

    Longer computations that keep going while the user carries on using the app. Typically, these methods are intended for job executions, long-running simulations, or any process that may take a significant amount of time to complete.

    See :ref:`asynchronous_execution`.

  .. grid-item-card:: :material-outlined:`sensors;1.4em;saf-concept-icon` Events - Live progress
    :class-card: concept-card

    Messages sent from the running computation to the UI so the user sees generations,
    percentages or logs appear in real time.

    See :ref:`events`.

  .. grid-item-card:: :material-outlined:`sync_alt;1.4em;saf-concept-icon` Frontend - The user interface
    :class-card: concept-card

    User-facing Dash pages that let the user interact with the backend and visualize results.

    See :ref:`dash_frontend`.

  .. grid-item-card:: :material-outlined:`inventory_2;1.4em;saf-concept-icon` Desktop installation - Shipping the app
    :class-card: concept-card

    Packaging the finished solution as a single file you can hand to any user, with
    no Python or setup on their side.

    See :ref:`installer`.

Prerequisites
=============

Before starting, make sure your workstation meets the requirements listed in the
:ref:`prerequisites` section and that you can run ``saf --version`` in a terminal.

You will also get more out of the tutorial if you are comfortable with:

- Basic Python (classes, decorators, type hints).
- The idea of a web application with a backend and a frontend.
- Reading small snippets of `Plotly Dash <https://dash.plotly.com/>`_ code.

Everything else — SAF concepts, ``ansys-saf-cli`` commands, Dash Mantine components—is introduced
progressively as you need it.

Learning path
=============

The tutorial is organized in five phases. Follow them in order — each phase builds on the
previous one.

.. grid:: 2
  :gutter: 4
  :class-container: onboarding-cards

  .. grid-item-card:: :material-outlined:`rocket_launch;1.75em` :ref:`game_of_life_initialization` (Phase 1/5)
    :class-card: highlight-card
    :link-type: doc
    :link: initialization
    :shadow: lg

    Create the solution from the SAF template, install it, and run the empty application.

  .. grid-item-card:: :material-outlined:`settings;1.75em` :ref:`game_of_life_business_logic` (Phase 2/5)
    :class-card: highlight-card
    :link-type: doc
    :link: business_logic
    :shadow: lg

    Add the pure Python engine that computes Game of Life generations.

  .. grid-item-card:: :material-outlined:`schema;1.75em` :ref:`game_of_life_backend` (Phase 3/5)
    :class-card: highlight-card
    :link-type: doc
    :link: backend
    :shadow: lg

    Wire the business logic into a SAF step model with typed fields, transactions and events.

  .. grid-item-card:: :material-outlined:`dashboard;1.75em` :ref:`game_of_life_frontend` (Phase 4/5)
    :class-card: highlight-card
    :link-type: doc
    :link: frontend
    :shadow: lg

    Build the Dash page that drives the backend and animates the grid in real time.

  .. grid-item-card:: :material-outlined:`inventory_2;1.75em` :ref:`game_of_life_package` (Phase 5/5)
    :class-card: highlight-card
    :link-type: doc
    :link: package
    :shadow: lg

    Ship the finished solution as a standalone desktop installer, for Windows or Linux.

.. tip::

    Every phase ends with a **Key takeaways** panel that recaps the SAF concepts you just met.
    Those panels double as a cheat sheet when you start writing your own solution.

.. toctree::
   :hidden:
   :maxdepth: 3

   initialization
   business_logic
   backend
   frontend
   package
