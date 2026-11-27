.. _release_maintenance_policy:

Release maintenance policy
##########################

Solution developers who build and deploy applications on top of SAF need to understand
how long a given release is maintained and what is expected of them regarding upgrades.
This page defines the official maintenance policy.

Policy rules
============

Rule 1: Fixes land only on the latest minor release
----------------------------------------------------

Within a maintained major branch, bug and vulnerability fixes are delivered **only on
top of the latest minor release**, following the version history forward.

.. important::

   SAF does **not** backport patches to older minor or patch releases within the same
   major version. If you need a fix, you must upgrade to the latest minor.

The following diagram illustrates this rule for version ``1.x``, where ``1.40`` is the latest minor:

- A bug is found in ``1.39.10``—the fix lands in ``1.40.6``, **not** ``1.39.11``.
  You must upgrade to ``1.40.6``.
- A bug is found in ``1.38.0``—the fix lands in ``1.40.7``, **not** ``1.38.1``.
  You must upgrade to ``1.40.7``.
- A bug is found in ``1.40.5``—the fix lands in ``1.40.8``. You upgrade to ``1.40.8``.

.. image:: /_static/images/release_maintenance_policy_fixes_on_latest_minor_release.svg
   :align: center
   :width: 70%
   :alt: SAF release maintenance policy diagram showing that bugs found in any minor are fixed only in the latest minor release


Rule 2: major version support window (6 months)
------------------------------------------------

When a breaking change occurs, a new **major version** is released. The **previous
major version (n-1)** continues to receive bug and vulnerability fixes for
**6 months** after the new major is published.

After the 6-month window, the former major branch reaches **end-of-life (EOL)** and
no further patches are provided. You must migrate to the latest major version.

.. warning::

   Only the latest minor release within the previous major receives fixes during the
   6-month maintenance window. Older minors within that major are not patched.

The following diagram illustrates this rule. When version ``2.0`` is released, the
``1.x`` branch enters a **6-month maintenance window**. During that window, only the
latest ``1.40.x`` patch receives fixes. Once the 6 months elapse, ``1.x`` reaches
**EOL** and is no longer supported—all users must migrate to ``2.x``.

.. image:: /_static/images/release_maintenance_policy_breaking_changes.svg
   :align: center
   :width: 70%
   :alt: SAF release maintenance policy diagram showing the 6-month maintenance window for the previous major version after a breaking change

Rule 3: Strict semantic versioning
-----------------------------------

SAF maintainers strictly follows `Semantic Versioning (SemVer) <https://semver.org/>`_:

- **Patch** (``x.y.Z``): Bug fixes and vulnerability patches only. No behavioral
  changes.
- **Minor** (``x.Y.0``): New features and additive changes. Fully backward compatible.
- **Major** (``X.0.0``): Breaking changes. A migration guide is provided.

This guarantees that upgrading within a major version is **safe and non-breaking**.
