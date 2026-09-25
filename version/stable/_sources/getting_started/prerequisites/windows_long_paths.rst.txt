.. _prerequisites_windows_long_paths:

Windows long paths
##################

.. note::

   This is a **Windows-only** prerequisite. If you are developing on another platform,
   you can skip this section.

SAF based solutions can easily exceed the default Windows maximum path length of 260 characters,
especially when working with Python packages that have deep directory structures. To avoid issues
with file operations, it's important to enable Windows long paths on your system.

To enable Windows long paths, follow these steps:

1. Navigate to :menuselection:`Settings > System > Advanced`.
2. Find the **Enable long paths** option and toggle it on.

.. image:: /_static/images/enable_long_paths.png
    :width: 60%
    :alt: Windows Long Path Settings
