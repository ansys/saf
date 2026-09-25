.. _mcp-server:

MCP server
##########

GLOW's **Solution API** server can optionally expose a `Model Context Protocol (MCP) <https://modelcontextprotocol.io>`_ server,
allowing AI agents and MCP-compatible clients to interact with your solution programmatically.

When enabled, the MCP server is automatically mounted on the GLOW API server process.
The MCP URL will be ``http://$SOLUTION_API_URL/$GLOW_MCP_PATH`` (default path: ``/sse``).
It's independent of how you launch the API Server, either through SAF Desktop Orchestrator, with a Docker compose file, using the GLOW CLI or manually launching the server.

The MCP server provides resources listing the available tools and expected solution workflow, and tools for managing projects,
setting and retrieving step fields, uploading and downloading single files, and running transaction methods,
both sync and long running.

.. important::
  This is an **experimental feature** and it's disabled by default. The following limitations apply:

  - Not supporting uploading/downloading directories, nor files within nested data structures (lists, dictionaries, custom objects, etc).
  - Not recommended to upload/download large files. At the moment, they are injected into the LLM context/output.
  - Not supporting websockets
  - Not supporting authentication. The MCP will be automatically disabled if :envvar:`GLOW_AUTH_DISABLED` is set to ``false``.

Enable the MCP server
=======================

The following steps assume you are using SAF CLI to manage your solution. For different environments, adjust accordingly.

1. Add the ``mcp`` extras group to the SAF GLOW Engine dependency in your solution's ``pyproject.toml``. Afterwards, update your lock file and install the new dependencies:

  .. code-block:: toml

      ansys-saf-glow-engine = {version = "^2.1", allow-prereleases=true, extras = ["mcp"]}

  .. code-block:: console

      saf execute my_solution "poetry lock"
      saf install my_solution

2. In your solution's ``.env`` file, enable MCP by setting:

  .. code-block:: text

      GLOW_MCP_DISABLED=False

3. Run your solution. No need to launch the UI:

  .. code-block:: console

      saf run --no-ui

4. Check the GLOW API logs and confirm that MCP is mounted. Look for an ``INFO`` line similar to:

  .. code-block:: text

      MCP mounted at path /sse


Configuration
=============

The MCP server is configured through the following environment variables:

.. list-table::
   :header-rows: 1
   :widths: 35 15 50

   * - Environment variable
     - Default
     - Description

   * - ``GLOW_MCP_DISABLED``
     - ``True``
     - Set to ``False`` to enable the MCP server. When ``True``, the MCP server is not started and
       none of the other MCP settings have any effect.

   * - ``GLOW_MCP_PATH``
     - ``/sse``
     - The subpath at which the MCP server is mounted on the GLOW API server.
       For example, with the default value and the API running on ``http://localhost:8000``,
       the MCP endpoint is reachable at ``http://localhost:8000/sse``.

   * - ``GLOW_MCP_TRANSPORT_MODE``
     - ``http``
     - The transport protocol used by the MCP server. Accepted values: ``http``, ``streamable-http``, ``sse``.


The ``SOLUTION.md`` file
========================

The MCP server reads an optional Markdown file named ``SOLUTION.md`` located in the **same directory as**
``definition.py`` of your solution. This file provides custom human-readable context to the AI agent using the MCP server.

File format
-----------

The file uses standard Markdown with two recognised level-2 headings:

.. code-block:: markdown

   # My Solution

   <this will be ignored>

   ## Instructions

   <Content describing the purpose of the solution and any important constraints for the AI agent.
   This text is passed to the MCP server as its system-level instructions.>

   ## Workflow

   <A step-by-step description of how to use the solution.
   This text is served via the `solution://workflow` resource.>

   ## Other section

   <this will be ignored>

Both sections are optional and any other section will be ignored. If a section is missing, a default is generated.

.. tip::
  Generic SAF concepts (what a project, step, field, or entity handle is, that transactions download and
  upload step fields, or that long-running transactions must be awaited with
  ``wait_for_longrunning_transaction``) are already explained to the agent via the ``saf://concepts``
  resource. Keep ``SOLUTION.md`` focused on what is specific to your solution: the meaning of its steps
  and fields, the order transactions must run in, and any domain constraints, rather than restating how
  SAF or its generic tools work.

Example
-------

.. code-block:: markdown

   # My Solution

   ## Instructions

   This solution runs structural analyses using Ansys Mechanical.
   Do not run `solve` until `setup_geometry` has completed successfully.

   ## Workflow

   1. In a fresh project, upload the geometry file on the `pre_processing` step, field `geometry_file`.
   2. Run `setup_geometry` to prepare the model.
   3. Set mesh parameters on the `meshing` step.
   4. Run `generate_mesh`.
   5. Run `solve`.
   6. Download the results on the `post_processing` step, field `result_file`.


Available resources
===================

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - URI
     - Description

   * - ``solution://workflow``
     - Returns the step-by-step workflow guide for the solution, sourced from the ``## Workflow`` section
       of ``SOLUTION.md``. If the section is missing, a default generated from the available solution's information is returned.

   * - ``saf://concepts``
     - Explains the generic SAF solution concepts (projects, steps, fields, entity handles, transactions,
       long-running transactions) that apply to every solution, regardless of its specific steps or fields.

   * - ``toolsets://definition``
     - Lists all available tools grouped into named tool sets (``project``, ``data``, ``transactions``).


Available tools
===============

**Project management**

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Tool
     - Description

   * - ``create_project``
     - Creates a new project in the solution and returns its name. Accepts an optional
       ``display_name``; if omitted, a name is generated automatically.

   * - ``list_projects``
     - Lists existing projects and their names, with optional pagination, ordering, and filtering.
       Use it to discover projects before using, exporting, or deleting them.

   * - ``delete_projects``
     - Deletes one or more projects and their data. This is destructive and irreversible.
       Deletion is attempted for every name, so a failure on one project does not prevent the others from
       being deleted. Returns the outcome per project name.

   * - ``import_project``
     - Imports a ``.safx`` project archive as a new project and returns its name.
       Because the archive is a binary zip, its content must be base64-encoded.

   * - ``export_project``
     - Exports a project as a ``.safx`` project archive.
       Because the archive is a binary zip, it is returned base64-encoded and must be decoded before
       being written to a file.

**Data management**

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Tool
     - Description

   * - ``set_fields``
     - Sets one or more step field values on an existing project.

   * - ``get_fields``
     - Gets the current values of one or more step fields from an existing project.

   * - ``upload_file``
     - Uploads binary content to an ``EntityHandle`` step field on an existing project.

   * - ``download_file``
     - Downloads binary content from an ``EntityHandle`` step field on an existing project.

**Transaction execution**

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Tool
     - Description

   * - ``<step_name>__<transaction_name>``
     - Runs a transaction method. One tool is registered per transaction method defined in the solution.
       If a regular synchronous transaction is called, it's a blocking call and the result (if there is) is returned at the end.
       If a long-running transaction is called, the call ends immediately and returns nothing. Use the tool ``wait_for_longrunning_transaction`` to wait for the transaction to complete and retrieve its result (if any).
       The tool's description starts with the transaction method's docstring, if it has one (otherwise a default
       sentence naming the transaction and step is used), followed by the step fields it downloads and uploads,
       its arguments, and its return type.

   * - ``wait_for_longrunning_transaction``
     - Waits for a previously started long-running transaction to complete and returns its result.

Connect an MCP client
========================

Once the MCP server is running, connect any MCP-compatible client (for example, a GitHub Copilot agent,
Claude Code, or a FastMCP client) to ``$SOLUTION_API_URL$GLOW_MCP_PATH``.

Example using the `FastMCP Python client <https://gofastmcp.com/clients/client>`_, assuming the Solution API is running at ``http://localhost:8000`` and the MCP server is mounted at the default value of ``/sse``:

.. code-block:: python

  import asyncio
  from fastmcp import Client
  from fastmcp.client.transports import StreamableHttpTransport


  async def main():
      transport = StreamableHttpTransport(url="http://localhost:8000/sse")
      async with Client(transport=transport) as client:
          resources = await client.list_resources()
          print([r.name for r in resources])
          tools = await client.list_tools()
          print([t.name for t in tools])


  asyncio.run(main())
