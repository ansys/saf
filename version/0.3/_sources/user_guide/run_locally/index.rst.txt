.. _ug-run-locally:

Run locally
############

SAF provides two methods to run a solution application on your local machine during development.

.. grid:: 3
   :gutter: 4
   :class-container: onboarding-cards

   .. grid-item-card:: :material-outlined:`terminal;1.75em` :ref:`user_guide_run_on_desktop`
      :class-card: highlight-card
      :link-type: doc
      :link: run_desktop
      :shadow: lg

      Run a solution using the SAF CLI ``saf run`` command. Ideal for desktop development with automatic service orchestration.

   .. grid-item-card:: :material-outlined:`dns;1.75em` :ref:`ug-run-docker-compose`
      :class-card: highlight-card
      :link-type: doc
      :link: docker_compose
      :shadow: lg

      Run a solution using Docker Compose for containerized execution.

.. toctree::
   :maxdepth: 2
   :hidden:

   run_desktop
   docker_compose
