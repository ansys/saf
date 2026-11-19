.. _examples_solution:

Set up the example solution
============================

The example solution provided in the ``saf/examples`` directory demonstrates selected SAF examples. Follow these instructions to install and run the solution.

#. Ensure you've fulfilled all requirements noted in the :ref:`prerequisites` section.

   .. note::

      We recommend using Python 3.11.5 or later for this example. This allows the
      solution to use SoupSieve 4.x, which avoids the vulnerable 2.x fallback on
      older Python versions. The advisories cover a descendant-combinator DoS
      (`GHSA-mmhr-3c5m-f64f <https://github.com/advisories/GHSA-mmhr-3c5m-f64f>`_)
      and an exponential ReDoS in selector compilation
      (`GHSA-6655-6qjp-jx7x <https://github.com/advisories/GHSA-6655-6qjp-jx7x>`_).

#. In a local clone of the ``saf`` repository, move to the ``examples`` folder:

   .. code-block:: bash

     cd saf/examples

#. Install the solution:

   .. code-block:: bash

       saf install -f

#. Run the solution:

   .. code-block:: bash

     saf run
