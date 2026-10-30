.. _bdm_introduction:

Introduction to BDM
###################

What is BDM?
============

SAF GLOW Engine leverages Blob Data Management (BDM) Python API as a core foundation
for file and directory management. BDM Python API integrated into SAF GLOW Engine is a Shared Technology Component (STC) that provides a robust, cloud-ready abstraction for
managing files and directories—referred to as BLOBs (Binary Large Objects)—within engineering workflows.

BDM Python API system is built around two fundamental concepts:

- **EntityHandle**: A lightweight reference that contains only metadata about a file or directory, not its actual contents
- **Storage Scopes**: Context-aware environments that manage the physical location and transfer of data

.. figure:: /_static/images/bdm_overview.png
   :alt: BDM Python API overview
   :align: center
   :width: 50%

   BDM Python API Overview

Key benefits of BDM Python API
-------------------------------

**Performance Optimization**
  The primary advantage of BDM Python API over legacy approaches is **significantly improved performance**.
  BDM eliminates unnecessary file copying between project, product instance, HPS, Data Repository, Minerva and method spaces
  by using intelligent caching. Files are only transferred when actually needed, dramatically reducing I/O overhead and execution time.

**Location Independence**
  Files are referenced by handles rather than absolute paths, enabling flexible data realization across different environments.
  This decoupling allows the same workflow to run seamlessly on Windows, Linux, cloud, or on-premises infrastructure without path-related issues.

**Optimized Data Transfer**
  BDM Python API implements smart caching strategies that minimize data movement. When multiple methods need the same file, it's cached once and shared,
  rather than being copied repeatedly. This is especially beneficial for large simulation files.

**Immutability and Safety**
  EntityHandles represent immutable data references, enabling safe sharing and caching across distributed systems. Note that the API cannot
  guarantee that nobody changes a file on disk at an inappropriate time. It is therefore incumbent upon the components to not modify a file
  after calling to read the contents into an EntityHandle, or to modify the BLOB handler's cache copy when consuming a file.

**Hierarchical Data Support**
  BDM treats directories as first-class entities, enabling efficient management of complex file structures and, maintaining relationships
  between related files.

Modern engineering challenges addressed
=========================================

BDM specifically addresses key challenges in contemporary engineering workflows:

- **Large Data Volumes**: Engineering simulations generate massive files that traditional file management approaches handle inefficiently
- **Distributed Execution**: Workflows spanning cloud, on-premises, and hybrid environments with different operating systems
- **Security and Collaboration**: Protected access to sensitive intellectual property while enabling team collaboration

By abstracting file operations through EntityHandles and Storage Scopes, BDM enables SAF GLOW Engine to deliver high-performance, scalable solutions
that work consistently across diverse deployment scenarios.
