.. _project_access_control:

Project access control
######################

By default, any user who can access a solution can open and modify every project in it. In an on-premises deployment where a team shares a server, this is often not what you want. Project access control makes projects private by default, lets their owners share them on purpose, and prevents two people from changing the same project at the same time.

The feature is part of SAF GLOW Engine: a solution gets it by configuration, with no changes to its backend code. Solution developers can add a ready-made banner to their pages and use the ``can_write`` flag to disable controls.

.. note::
   Project access control is disabled by default. When it is disabled, nothing changes: the access API routes return 404, ``ProjectInfo.access`` is ``null``, and the UI components render nothing.


Enabling project access control
===============================

Set :envvar:`GLOW_PROJECT_ACCESS_CONTROL_ENABLED` to ``True``. The feature identifies users by the ``sub`` claim of their access token, so authentication validation must be enabled too (see :ref:`auth`). The API server refuses to start if :envvar:`GLOW_PROJECT_ACCESS_CONTROL_ENABLED` is ``True`` while :envvar:`GLOW_AUTH_DISABLED` is ``True``.

.. code-block:: bash

    GLOW_DEPLOYMENT=DockerCompose
    GLOW_AUTH_DISABLED=False
    GLOW_AUTH_ISSUER_URL=https://your-keycloak-server/auth/realms/your-realm
    GLOW_AUTH_CLIENT_ID=your_client_id

    GLOW_PROJECT_ACCESS_CONTROL_ENABLED=True

The feature targets on-premises (web) deployments. It is not meant for desktop deployments, where authentication is typically off.

.. note::
   GLOW stores and receives only user ids (the ``sub`` claim). It never stores e-mail addresses, user names, or display names. Resolving a user name to an id, and an id to a display name, is the job of the UI server (see :ref:`project_access_user_directory`).


Roles
=====

Every project has exactly one owner and any number of viewers. At any moment, at most one of them also holds the write lock.

.. list-table:: Roles on a project
   :header-rows: 1
   :widths: 18 32 50

   * - Role
     - How you get it
     - What you can do
   * - **Owner**
     - Creating or importing the project, an ownership transfer, or an assignment by a super admin.
     - Everything a viewer can do, plus: share and unshare the project, transfer ownership, take over the write lock at any time, approve or deny write requests, and delete the project.
   * - **Viewer**
     - The owner shares the project with you.
     - Read everything (steps, fields, files, results, method states, events, export). Request write access.
   * - **Lock holder**
     - You are the owner or a viewer and hold the write lock.
     - All writes. Release the lock. Approve or deny write requests, which hands the lock over.
   * - **Super admin**
     - You hold one of the roles listed in :envvar:`GLOW_AUTH_SUPER_ADMIN_ROLES`.
     - Manage project metadata on all projects: assign or reassign the owner, force-release a lock, mark a stuck method as failed, and delete. A super admin **cannot** read or write project contents unless they are also a member.

Users who have no role on a project do not see it. It is absent from lists, and a direct request for it returns 404 (not 403), so its existence is not revealed.

Ownership transfer
------------------

- An owner can transfer ownership only to an existing member. A super admin can assign any user id, and that user becomes a member.
- The previous owner stays on the project as a viewer. The new owner can remove them.
- The lock and the pending write requests are unchanged. The right to approve requests follows the role, so it moves to the new owner.
- Ownership transfers and super admin assignments are recorded in the audit log.

Existing projects
-----------------

When you enable the feature on a database that already has projects, those projects have no owner. They are *orphans*: only super admins see them, until a super admin assigns an owner. Nothing is migrated automatically.


The write lock
==============

All writes to a project require its write lock. The following rules apply.

- The creator of a project (or the user who imports it) holds the lock.
- If nobody holds the lock, any member can acquire it directly, without approval.
- The holder can release the lock at any time.
- The owner can take over the lock at any time, without approval.
- The lock **expires** after :envvar:`GLOW_PROJECT_LOCK_IDLE_TIMEOUT` seconds (default: 28800, 8 hours) without a write by the holder. Expiry is evaluated when the lock is read or contended.
- **The lock never moves while a transaction is running on the project.** This applies to approval, take-over, release, force release, unsharing, and expiry. The attempt fails with 409 so that the results of a solve started by one user are never written under the lock of another user.
- If a transaction is stuck as running because its runner died, the owner or a super admin can mark it as failed once it has run for more than :envvar:`GLOW_PROJECT_STUCK_METHOD_TIMEOUT` seconds (default: 86400, 24 hours). This unblocks lock transfers and is recorded in the audit log.

Write requests
--------------

A member who does not hold the lock can ask for it:

- A user can have at most one pending request per project. Several users can have a pending request at the same time. If the lock is free, requesting is rejected with 409 and the user acquires the lock instead.
- The owner or the current holder can **approve** or **deny** a request. Approving moves the lock to the requester, and the previous holder becomes read-only.
- The requester can **withdraw** the request.
- When the lock is released, expires, or is taken over, pending requests stay pending.
- Requests are not notified outside the application.

What counts as a write
----------------------

The following operations require the write lock:

- Running a transaction, and updating the state of a method.
- Updating a step (REST ``PATCH`` or the ``update_project_steps_with_json`` GraphQL mutation).
- Creating, updating, or deleting an instance.
- Uploading a blob.
- Updating the display name or description of a project, and upgrading a project.
- Acquiring or releasing BDM locks.
- Posting a step event.

Reading a project, exporting it, reading steps, fields, blobs and method states, GraphQL queries, and event streams require membership.

Transactions keep working after they start, even though the method runner calls back into the API server with the API key rather than the token of the user. The runner carries the id of the user who started the transaction in an ``x-glow-on-behalf-of`` header. The API server honors this header only on requests that also carry a valid API key.


Status codes
============

.. list-table:: Status codes returned when project access control is enabled
   :header-rows: 1
   :widths: 12 88

   * - Code
     - Meaning
   * - 403
     - A member attempted an action reserved to another role, for example a viewer trying to share a project or someone other than a super admin trying to force-release a lock.
   * - 404
     - The user is not a member of the project (or the project does not exist). Also returned by all the access routes when the feature is disabled.
   * - 409
     - The lock cannot move because a transaction is running, or a write request cannot be created because the lock is free.
   * - 423
     - The caller does not hold the write lock. The response body has a ``detail`` object with a ``holder_id`` (the id of the current holder, or ``null`` if nobody holds the lock, in which case the caller must acquire it first) so a UI can explain what happened.

.. code-block:: json

    {
        "detail": {
            "message": "Another user holds the write lock of this project.",
            "holder_id": "2c8f0c1e-3c1a-4f6e-9a54-1d3f6a7b8c9d"
        }
    }


Settings
========

.. list-table:: Project access control settings
   :header-rows: 1
   :widths: 35 45 20

   * - Environment variable
     - Description
     - Default
   * - :envvar:`GLOW_PROJECT_ACCESS_CONTROL_ENABLED`
     - Enables project access control. Requires :envvar:`GLOW_AUTH_DISABLED` to be ``False``.
     - ``False``
   * - :envvar:`GLOW_PROJECT_LOCK_IDLE_TIMEOUT`
     - Seconds without a write by the holder after which the write lock is released.
     - ``28800``
   * - :envvar:`GLOW_PROJECT_STUCK_METHOD_TIMEOUT`
     - Seconds after which a running method is considered stuck and the owner or a super admin can mark it as failed.
     - ``86400``
   * - :envvar:`GLOW_AUTH_ROLES_CLAIM`
     - Dotted path of the access token claim that holds the roles of the user. The placeholder ``{client_id}`` is replaced with :envvar:`GLOW_AUTH_CLIENT_ID`. Examples: ``roles`` (Microsoft Entra ID) and ``groups`` (Okta). The same claim is used by :envvar:`GLOW_AUTH_REQUIRED_ROLES` and :envvar:`GLOW_AUTH_BYPASS_ROLES`.
     - ``resource_access.{client_id}.roles``
   * - :envvar:`GLOW_AUTH_SUPER_ADMIN_ROLES`
     - Comma-separated list of roles. A user who has any of them is a super admin. If empty, there is no super admin.
     - empty
   * - :envvar:`GLOW_UI_USER_DIRECTORY`
     - User directory that the UI server uses to find users: ``none``, ``keycloak``, ``scim``, or ``msgraph``. See :ref:`project_access_user_directory`.
     - ``none``
   * - :envvar:`GLOW_UI_KEYCLOAK_URL`, :envvar:`GLOW_UI_KEYCLOAK_REALM`, :envvar:`GLOW_UI_KEYCLOAK_CLIENT_ID`, :envvar:`GLOW_UI_KEYCLOAK_CLIENT_SECRET`
     - Connection settings of the Keycloak user directory.
     - ``None``

The access state of a project is also pushed to clients over a WebSocket. :envvar:`GLOW_PROJECT_ACCESS_POLL_INTERVAL` (default: ``1.0``, in seconds) sets how often the API server checks a project for changes to push.


Access API
==========

The access API is available at the following routes of the API server. Each one returns the new access state of the project (a ``ProjectAccess`` document) unless noted otherwise.

.. list-table:: Access API routes
   :header-rows: 1
   :widths: 10 50 40

   * - Method
     - Route
     - Who
   * - GET
     - ``/access/me`` (returns the user id of the caller and whether they are a super admin)
     - Any user
   * - GET
     - ``/access/audit`` (the audit log, most recent first)
     - Super admins
   * - GET
     - ``/projects/{project_id}/access``
     - Members and super admins
   * - POST
     - ``/projects/{project_id}/access/members`` (body: ``{"user_id": ...}``)
     - Owner
   * - DELETE
     - ``/projects/{project_id}/access/members/{user_id}``
     - Owner
   * - POST
     - ``/projects/{project_id}/access:transfer-ownership``
     - Owner
   * - POST
     - ``/projects/{project_id}/access:assign-owner``
     - Super admins
   * - POST
     - ``/projects/{project_id}/lock:acquire``
     - Members
   * - POST
     - ``/projects/{project_id}/lock:release``
     - Holder
   * - POST
     - ``/projects/{project_id}/lock:take-over``
     - Owner
   * - POST
     - ``/projects/{project_id}/lock:force-release``
     - Super admins
   * - POST
     - ``/projects/{project_id}/write-requests``
     - Members who do not hold the lock
   * - POST
     - ``/projects/{project_id}/write-requests/{request_id}:approve`` or ``:deny``
     - Owner or holder
   * - POST
     - ``/projects/{project_id}/write-requests/{request_id}:withdraw``
     - Requester
   * - POST
     - ``/projects/{project_id}/methods:fail-stuck``
     - Owner or super admins

A WebSocket at ``/events/projects/{project_id}/access`` sends the access state when a client connects and each time it changes. Only members can connect.

Projects returned by the API have an ``access`` field with a summary (owner id, holder id, role of the user, and number of pending requests). It is ``null`` when the feature is disabled.


Using project access control in a solution
==========================================

DashClient helpers
------------------

In Dash callbacks, :py:class:`~ansys.saf.glow.client.DashClient` has helpers that act on behalf of the current user:

- ``get_project_access(project_id)``: Returns a :py:class:`~ansys.saf.glow.client.ProjectAccess` (role of the user, ``can_write``, holder, pending requests), or ``None`` if the feature is disabled.
- ``acquire_lock(project_id)``, ``release_lock(project_id)``, and ``take_over_lock(project_id)``.
- ``request_write_access(project_id)``, ``withdraw_request(project_id, request_id)``, ``approve_request(project_id, request_id)``, and ``deny_request(project_id, request_id)``.
- ``share_project(project_id, user_id)`` and ``unshare_project(project_id, user_id)``.
- ``resolve_user(identifier)`` and ``display_names(user_ids)``, which use the user directory of the UI server.
- ``create_access_listener(project_id, id)``: Returns a WebSocket component that receives the access state each time it changes.

The framework does not disable the inputs of your pages for you. The API server enforces the rules, and your pages use ``can_write`` to disable the controls that modify the project. For example:

.. code-block:: python

    from ansys.saf.glow.client import DashClient, callback
    from ansys.solutions.dash_super_components import ProjectAccessBanner
    from dash_extensions.enrich import Input, Output, State

    ACCESS_BANNER_ID = "my-step-access-banner"


    @callback(
        Output("my-step-calculate", "disabled"),
        Input(ProjectAccessBanner.ids.listener(ACCESS_BANNER_ID), "message"),
        State("url", "pathname"),
    )
    def disable_calculate_without_write_access(message, project: MySolution):
        access = DashClient.get_project_access(project.project_id)
        return access is not None and not access.can_write

Banner
------

``ProjectAccessBanner`` from ``ansys.solutions.dash_super_components`` shows who may edit the project and lets the user act on the lock. Add it once at the top of the layout of a page:

.. code-block:: python

    from ansys.solutions.dash_super_components import ProjectAccessBanner


    def layout(project: MySolution):
        return html.Div(
            [
                ProjectAccessBanner(project_id=project.project_id, aio_id=ACCESS_BANNER_ID),
                ...
            ]
        )

It updates live and shows:

- "You are editing this project." with a **Release** button.
- "Nobody is editing this project." with a **Start editing** button.
- "Read-only - <name> is editing." with a **Request write access** button, or **Withdraw** if the user has already asked. The owner also gets a **Take over** button.
- An **Approve** and **Deny** prompt for each pending request, for the owner and the holder.

It renders nothing when project access control is disabled. The step templates (calculator, HPS simple job, HPS parametric study, and Geometry) include the banner and disable their main action button while the user does not hold the lock.

Projects dashboard
------------------

When the feature is enabled, the projects dashboard lists only the projects that the user can access, with **Owner** and **Editing now** columns. Its context menu depends on the role of the user: share, take over or release the lock, approve or deny requests, request or withdraw write access, and, for super admins, assign an owner or force-release a lock. Super admins can also filter on projects that have no owner. The dashboard has a **Copy my user id** button, so users can tell an owner their id when no user directory is configured.


.. _project_access_user_directory:

User directory
==============

OpenID Connect has no standard way for one user to look up another. To share a project, the owner types an e-mail or a user name, and something has to turn it into a user id. This lookup lives in the Dash UI server, not in the API server, so that credentials never reach the API and the API never stores names. The UI server exposes ``/_saf/users/resolve`` and ``/_saf/users/names`` to the browser (for the projects dashboard), and the DashClient helpers ``resolve_user`` and ``display_names`` to Python. Callers must be authenticated and results are never persisted.

Select the directory with :envvar:`GLOW_UI_USER_DIRECTORY`:

.. list-table:: User directories
   :header-rows: 1
   :widths: 15 85

   * - Value
     - Behavior
   * - ``none``
     - Default. The text that the user types is used as the user id, and ids are displayed as they are. Sharing works with raw ids, which users can copy from the dashboard.
   * - ``keycloak``
     - Looks users up with the Keycloak admin REST API. See below.
   * - ``scim``, ``msgraph``
     - Placeholders for SCIM 2.0 and Microsoft Graph. They are an extension point only. Selecting one of them makes the UI server fail at startup with a "not implemented yet" error.

Keycloak
--------

Create a client in the realm of your solution with the following settings:

- **Client authentication** on and **Service accounts roles** on.
- In the service account roles of the client, assign only the ``view-users`` role of the ``realm-management`` client.

Then configure the UI server:

.. code-block:: bash

    GLOW_UI_USER_DIRECTORY=keycloak
    GLOW_UI_KEYCLOAK_URL=https://your-keycloak-server/auth
    GLOW_UI_KEYCLOAK_REALM=your-realm
    GLOW_UI_KEYCLOAK_CLIENT_ID=your-directory-client
    GLOW_UI_KEYCLOAK_CLIENT_SECRET=the-client-secret

A name matches only if it is an exact match of an e-mail or a user name. If several users match an e-mail, nothing is returned. If Keycloak is unavailable, the user directory routes return 502. Display names are cached in memory for five minutes.

.. note::
   Keep the client secret out of your images and your version control. Use a secret store or a Docker secret to provide it.
