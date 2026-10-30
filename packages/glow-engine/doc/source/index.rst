.. _glow-api-index:

#############
API reference
#############

GLOW provides Pythonic APIs that you can use to develop solutions. This documentation provides details on the core classes, functions, and methods in the GLOW API.

.. grid:: 3
    :gutter: 4
    :class-container: onboarding-cards

    .. grid-item-card:: :material-outlined:`api;2em` Solution API
        :class-card: highlight-card
        :link-type: doc
        :link: solution
        :shadow: lg

        Provides the core functionality for managing and running solutions using GLOW.

    .. grid-item-card:: :material-outlined:`api;2em` Runtime API
        :class-card: highlight-card
        :link-type: doc
        :link: runtime
        :shadow: lg

        Enables the integration of a GLOW solution (a guided workflow application) with the GLOW infrastructure.

    .. grid-item-card:: :material-outlined:`api;2em` Client API
        :class-card: highlight-card
        :link-type: doc
        :link: client
        :shadow: lg

        Enables programs, including a Dash UI server, to access a remote GLOW server that provides the guided workflow service for a solution.

    .. grid-item-card:: :material-outlined:`api;2em` Product instance API
        :class-card: highlight-card
        :link-type: doc
        :link: product_instance
        :shadow: lg

        Enables launching, connecting to, and managing instances of Ansys products.

    .. grid-item-card:: :material-outlined:`api;2em` HPS API
        :class-card: highlight-card
        :link-type: doc
        :link: hps
        :shadow: lg

        Enables transaction methods to start HPS jobs and parametric studies, and then to request data from those jobs and studies.

    .. grid-item-card:: :material-outlined:`api;2em` CLI API
        :class-card: highlight-card
        :link-type: doc
        :link: cli
        :shadow: lg

        Provides the command-line interface for running GLOW API and UI servers and analysis commands.


.. toctree::
   :maxdepth: 1
   :hidden:

   solution
   runtime
   client
   product_instance
   hps
   cli
