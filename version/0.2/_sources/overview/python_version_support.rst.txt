.. _python_version_support:

Python version support
######################

Strategy
========

SAF SDK declares support for all Python versions that are actively maintained by
the `Python core team <https://devguide.python.org/versions/>`_ **and** compatible
with its key dependencies, namely `Dash <https://dash.plotly.com/>`_ and
the simulation libraries it integrates with. This approach keeps SAF SDK
aligned with the broader Python ecosystem while ensuring that developers
working in corporate environments are not forced into premature Python upgrades.

When a Python version reaches its end-of-life (EOL) date, SAF SDK drops support
for it in the next release cycle. Conversely, when a new Python version becomes
stable **and** is supported by both Dash and the PyAnsys libraries that SAF SDK
depends on, SAF SDK adds support for it.

Currently supported versions
============================

.. list-table::
   :header-rows: 1
   :widths: 20 20 30

   * - Python version
     - Status
     - Notes
   * - 3.10
     - ⛔ Dropped
     -
   * - 3.11
     - ✅ Supported
     -
   * - 3.12
     - ✅ Supported
     -
   * - 3.13
     - ✅ Supported
     -
   * - 3.14
     - ✅ Supported
     -

Testing approach
================

To balance quality with development efficiency, SAF SDK applies the following
testing strategy:

- **Continuous integration (CI):** Pull-request pipelines run the full test
  suite against a focused subset of Python versions (typically the lowest and
  highest supported versions). This keeps feedback cycles fast without
  sacrificing coverage of version-specific behavior.

- **Release certification:** Before each release, the test suite is executed
  against **all** declared Python versions to certify compatibility across the
  full support range.

This means that while all listed versions are officially supported (and bugs
reported against any of them will be investigated), the deepest automated
coverage during day-to-day development targets the boundary versions.

