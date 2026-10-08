#####################
Dash Super Components
#####################

|python| |pypi| |GH-CI| |Apache| |ruff|

.. |python| image:: https://img.shields.io/pypi/pyversions/ansys-solutions-dash-super-components?logo=python&logoColor=white&label=Python
   :target: https://pypi.org/project/ansys-solutions-dash-super-components/
   :alt: Python

.. |pypi| image:: https://img.shields.io/pypi/v/ansys-solutions-dash-super-components.svg?logo=pypi&logoColor=white&label=PyPI
   :target: https://pypi.org/project/ansys-solutions-dash-super-components/
   :alt: PyPI

.. |GH-CI| image:: https://img.shields.io/github/actions/workflow/status/ansys/saf/ci_cd_pr.yml?branch=main&label=CI-CD&logo=github
   :target: https://github.com/ansys/saf/actions/workflows/ci_cd_pr.yml?query=branch%3Amain
   :alt: GH-CI

.. |Apache| image:: https://img.shields.io/badge/License-Apache2.0-white.svg?labelColor=black
   :target: https://www.apache.org/licenses/
   :alt: Apache

.. |ruff| image:: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
   :target: https://github.com/astral-sh/ruff
   :alt: Ruff


Overview
========

Dash Super Components is a collection of pre-assembled, high-level UI components
built on top of the `Dash Mantine Components (DMC) <https://www.dash-mantine-components.com/>`_
library. The components implement common patterns in simulation web app UIs, reducing
frontend development effort by packaging UI logic and layout conventions into smart
building blocks.

Dash is a trademark of Plotly Technologies Inc. This project is not affiliated with, endorsed by,
or sponsored by Plotly Technologies Inc.


Installation
============

Ensure you have all the necessary `prerequisites`_.

The ``ansys-solutions-dash-super-components`` package supports Python 3.11
through 3.14 on Windows and Linux.

To install Dash Super Components, run:

.. code-block:: bash

   pip install ansys-solutions-dash-super-components


Documentation
=============

Visit the `official documentation`_ for detailed information on how to use Dash Super Components.
Check the `API reference`_ for a complete list of classes, methods, and usage examples.

Quick start
-----------

.. important::

   Dash Super Components use the ``callback`` decorator and other utilities from
   ``dash_extensions.enrich``. Your application **must** use
   ``dash_extensions.enrich.DashProxy`` instead of the standard ``dash.Dash``.
   Using ``dash.Dash`` directly causes the internal callbacks of the components
   to fail.

The following minimal example shows how to add the ``DualInputRangeSlider``
component to a Dash application:

.. code:: python

   import dash_mantine_components as dmc
   from dash import _dash_renderer
   from dash_extensions.enrich import DashProxy, html
   from ansys.solutions.dash_super_components import DualInputRangeSlider

   # Required for Dash 2.x
   _dash_renderer._set_react_version("18.2.0")

   app = DashProxy(__name__)

   app.layout = dmc.MantineProvider(
       children=[
           html.Div(
               [
                   DualInputRangeSlider(
                       aio_id="example-slider",
                       min=0,
                       max=100,
                       value=[20, 80],
                   )
               ],
               style={"padding": "40px"},
           )
       ]
   )

   if __name__ == "__main__":
       app.run(debug=True)

Run the example with ``python app.py`` and open ``http://127.0.0.1:8050`` in
your browser.

For detailed instructions on how to get started with Dash Super Components, see the
`getting started guide <https://saf.ansys.com/version/stable/getting_started/index.html>`_
in the documentation.

For more complex examples, see the `gallery applications
<https://github.com/ansys/saf/tree/main/packages/dash-super-components/examples/gallery_apps>`_
in the repository.


Troubleshooting
===============

For troubleshooting or reporting issues, please open an issue in the `project repository`_.

Please follow these steps to report an issue:

- Go to the project repository.
- Click on the ``Issues`` tab.
- Click on the ``New Issue`` button.
- Provide a clear and detailed description of the issue you are facing.
- Include any relevant error messages, code snippets, or screenshots.

Additionally, you can refer to the `official documentation`_ for additional
resources and troubleshooting guides.


Contribute
==========

Contributions are welcome!
If you would like to contribute, please follow the guidelines provided in the `Contribute`_
section of the official documentation.


License
=======

You can find the full text of the license in the `LICENSE`_ file.


Changelog
=========

The changelog section provides a summary of notable changes for each version of
Dash Super Components. It helps you keep track of updates, bug
fixes, new features, and improvements made to the project over time.

To view the complete changelog, visit the project repository and navigate
to the `CHANGELOG`_ file. It provides a comprehensive list of changes
categorized by version, along with brief descriptions of each change.


.. _official documentation: https://saf.ansys.com/
.. _project repository: https://github.com/ansys/saf/
.. _prerequisites: https://saf.ansys.com/version/stable/getting_started/prerequisites/index.html
.. _API reference: https://saf.ansys.com/version/stable/api/dash-super-components/index.html
.. _Contribute: https://saf.ansys.com/version/stable/contribute/index.html
.. _LICENSE: https://github.com/ansys/saf/blob/main/packages/dash-super-components/LICENSE
.. _CHANGELOG: https://github.com/ansys/saf/blob/main/packages/dash-super-components/CHANGELOG.md
