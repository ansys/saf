.. _troubleshooting_dependencies:

Dependencies
############



Manage solution dependencies
==============================

Update package version dependencies
-------------------------------------

Problem
~~~~~~~

The solution has an direct or indirect dependency on a version of a package with a functional defect, vulnerability or overly restrictive license.
Typically a vulnerability will be detected using a third party tool such as `MEND <https://docs.mend.io/>`_
or `pip-audit <https://github.com/pypa/pip-audit>`_.

.. note::
    * As per Pythonic best practice the SAF SDK packages do *not* contain direct
      dependencies to packages *solely* to ensure that a solution will
      not have vulnerabilities. This means that the SAF SDK is not necessarily defective if a vulnerability is discovered in a dependency of a SAF SDK package in the context of a Solution.
    * Solution developers are responsible for ensuring that their solutions do not
      introduce vulnerabilities through their dependencies.
      Solution developers are strongly encouraged to use CI/CD actions to scan for vulnerabilities.
    * This section is provided as guide to upgrading packages which allows the
      developer to eliminate known vulnerabilities.
    * Solution developers should raise defect reports whenever the SAF SDK is
      constraining dependencies such that vulnerabilities cannot be avoided.
      Solution developers are expected to follow the process described in this section to determine if this is the case when a vulnerability is discovered.

Solution
~~~~~~~~
The problem is fixed by changing the version of the dependency to an acceptable version of the package.
Before starting the update process it is a good idea to first determine what version of the given package is going to fix the issue at hand.
Typically the latest version of the given package is chosen.

The versions of a package that can be installed is determined by the constraints of other packages that depend on it as well as the
constraints imposed on the dependency in the ``pyproject.toml`` file managed by poetry. The latest compatible version that satisfies all constraints may
not be the latest version of the package.

To proceed with a fix do the following in order:

.. _use-poetry-update:

Upgrade a dependency to the latest compatible version
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
With the solution virtual environment activated run the following command to determine the latest version of the package
that is compatible with the other packages in the solution.

.. code-block:: bash

    poetry update --dry-run --with=ui,doc,tests,build,style,desktop <package-name>

The package name is the name used for the package in `pypi <https://pypi.org/>`_.

This command will report the version the package could be upgraded to.
The reported version may not be the required version in which case skip to :ref:`the next section <use-poetry-add>`.
If the command does not propose changes then no upgrade is possible in which case skip to :ref:`the next section <use-poetry-add>`.
The command may report other changes that are required to accommodate the upgrade which may not be acceptable
in which case skip to :ref:`the next section <use-poetry-add>`.

If the reported version is acceptable and the other changes that the command has reported are also acceptable then execute the following command

.. code-block:: bash

    poetry update --with=ui,doc,tests,build,style,desktop <package-name>

.. warning::
   :class: important

   This command will modify the package versions that your solution is using.  You should re-test and code check your solution before committing changes.
   Be especially careful if the major version of any package has changed with the upgrade.

The ``poetry update`` command will update the ``poetry.lock`` file. This change should be committed to source control.
No further action is required.

Further information can be found in the `Poetry documentation for the update command <https://python-poetry.org/docs/cli/#update>`_.

.. _use-poetry-add:

Correct simple constraints that are limiting a package upgrade
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Perform the instructions in the following order:

Determine the Poetry group containing the package
"""""""""""""""""""""""""""""""""""""""""""""""""""

Before proceeding further you should determine the poetry dependency group that the given package is in.
Search the ``pyproject.toml`` for the pypi name of the package.  It should be listed with its dependency constraint
below a section heading of one of the forms:

- ``[tool.poetry.group.<group>.dependencies]``
    In this case ``group`` is the name of the group containing the package.

- ``[tool.poetry.dependencies]``.
    In this case the group is ``main``.

You need to run different commands depending on whether the group is ``main`` or not.

If the package is not listed in the ``pyproject.toml`` you will have to determine a group for it to reside.
SAF Solutions generated with the SAF CLI have the following groups:

- ``main`` - deployed - contains the core functionality of the solution
- ``ui`` - deployed - user interface components
- ``doc`` - documentation
- ``tests`` - unit and integration tests
- ``build`` - build scripts and configurations
- ``style`` - code style and formatting
- ``desktop`` - deployed on desktop - desktop integration

If you know for sure that the package is required for execution of the Solution transaction methods then ``main`` is the correct choice.

Dry run of package constraint change
""""""""""""""""""""""""""""""""""""

With the solution virtual environment activated run the following command to determine the constraints that are limiting the package upgrade.
This command will report the actions that would result from changing the constraints for the package to support the latest version.

.. tab-set::

  .. tab-item:: 1️⃣group is ``main``
    :name: group-is-main-dry-run

    .. code-block:: bash

        poetry add --dry-run <package-name>@latest

  .. tab-item:: 2️⃣group is not ``main``
    :name: group-is-not-main-dry-run

    .. code-block:: bash

        poetry add --dry-run --group=<group> <package-name>@latest

The use of ``latest`` will change the dependency constraint so that the package must be the latest version or later but
never the next major version or a version after the next major version (a "^" constraint is used).
Substitute a version constraint string instead of ``latest`` as required, for example, if you want to specify a specific range of versions
as a new constraint.
See `the poetry dependency specification documentation <https://python-poetry.org/docs/dependency-specification/#caret-requirements>`_ for more details.

If this command reports dependency conflicts then proceed to :ref:`the section covering complex conflicts <fix-complex-constraint>`.
Review the proposed changes carefully.
If the changes are not acceptable proceed to :ref:`the section covering complex conflicts <fix-complex-constraint>`.

Change a package constraint
"""""""""""""""""""""""""""

If you are happy with the changes then proceed with the following command (again substitute your preferred version constraint as required).

.. tab-set::

  .. tab-item:: 1️⃣group is ``main``
    :name: group-is-main-run

    .. code-block:: bash

      poetry add <package-name>@latest

  .. tab-item:: 2️⃣group is not ``main``
    :name: group-is-not-main-run

    .. code-block:: bash

      poetry add --group=<group> <package-name>@latest

.. warning::

   This command will modify the package versions that your solution is using beyond versions that where previously allowed by the old constraints.
   You should re-test and code check your solution before committing changes.
   Be especially careful if the major version of any package has changed with the upgrade.

The ``poetry add`` command will update the ``poetry.lock`` and ``pyproject.toml`` files. These changes should be committed to source control.
No further action is required.

Further information command can be found in the `Poetry documentation for the add command <https://python-poetry.org/docs/cli/#add>`_.

.. _fix-complex-constraint:

Correct complex constraints that limit a package upgrade
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you are reading this section then you are attempting to resolve a complex constraint issue that is limiting a package upgrade.
You should have some diagnostic information generated by a poetry command that is attempting to describe a conflict between
package versions that your solution is dependent on.  You can use the following command to display the package dependency tree for
your solution which may help you understand the issue more clearly.

.. code-block:: bash

   poetry show --tree

Unfortunately this command doesn't show the dependency constraints that have been applied directly to your solution.
To see these view the pyproject.toml and search for the name of the package you are interested in.

Determining the best course of action is often not easy.
Often you will need to change the constraints of another package via ``poetry add`` (as described in :ref:`the previous section <use-poetry-add>`) before
updating the package which originally needed to be upgraded via ``poetry update`` (as described in :ref:`an earlier section <use-poetry-update>`).
As a general rule aim for modification to package constraints with ``poetry add`` at the highest level in the dependency tree.

Typically, you have two options to resolve the issue:

1. Change version constraints in the solution.
    Change the constraint for a conflicting package A that is not the original package B that needs to be upgraded.
    In this scenario A has a direct or indirect dependency on B. Your solution has dependency on an old version of A
    which is constraining the dependency on B to an old version.
    Use ``poetry add`` on package A with a specific version constraint as described in :ref:`the previous section <use-poetry-add>` to change
    the constraints on A.
    Then you can apply ``poetry update`` for package B (as described in :ref:`an earlier section <use-poetry-update>`)

2. Raise an issue with one of the package maintainers to resolve the conflict.
    This makes sense if you have an unconstrained dependency on package A which has a constrained dependency on a
    vulnerable version of package B when a later version of B without the vulnerability exists.
    In which case you should raise an issue for package A. Maintainers are usually responsive to
    fixing issues that are raised with their packages, especially if the issue relates to a security vulnerability.
    If you choose this path then you will need to wait for the package maintainer to fix the issue and release a new version of the package
    before you can update your solution. At which point you'll need to introduce a constraint for the new package version on package A
    using ``poetry add`` as described in :ref:`the previous section <use-poetry-add>`.
    Then you can apply ``poetry update`` for package B (as described in :ref:`an earlier section <use-poetry-update>`).