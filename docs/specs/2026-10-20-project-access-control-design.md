# Per-user project access control with a single-writer lock — design

Date: 2026-10-20
Status: draft for review
Revised: 2026-11-27 — GLOW owns project permissions and can run without App Portal; memberships are
stored by a pluggable backend (GLOW database by default, OpenFGA interface placeholder). See 2.10.

## 1. Intent

In an on-premises web deployment of a SAF solution (GLOW API + PostgreSQL + an OIDC identity
provider), any authenticated user can today open and modify any project
(`doc/source/user_guide/backend/authn_authz/authentication.rst:43`). Teams sharing a server
need projects to be private by default, shareable on purpose, and protected from two people
changing the same project at once.

The framework (not each solution) must provide this, so every SAF solution gets it by
configuration, and solution developers get UI building blocks to expose it with minimal code.

Today, in Ansys App Portal deployments, App Portal writes project permissions into its OpenFGA and
GLOW relies on that. GLOW must instead be the single authority on project permissions and must work
with no App Portal at all (a strong requirement). App Portal becomes a consumer of GLOW's access API.
Where GLOW stores memberships is a deployment choice behind one interface (section 2.10).

## 2. Behaviour

### 2.1 Roles on a project

| Role | How you get it | What you can do |
|---|---|---|
| **Owner** | Creating (or importing) the project; ownership transfer; super admin assignment | Everything a viewer can, plus: share/unshare, transfer ownership, take over the lock at any time, approve/deny write requests, delete the project |
| **Viewer** | Owner shares the project with you | Read everything (steps, fields, files, results, method states, events, export). Request write access. |
| **Lock holder** | Exactly one of owner/viewers at a time, or nobody | All writes. Release the lock. Approve/deny write requests (which hands the lock over). |
| **Super admin** | Configurable OIDC role (see 2.6) | Project *metadata* on all projects; assign/reassign owner; force-release a lock; delete. **No access to project contents.** |

There is exactly one owner per project. The owner is always also a member with view access.

Ownership transfer (decided while writing this design):
- An owner can transfer only to an existing member. A super admin can assign any user id, and that user
  becomes a member.
- The previous owner stays on the project as a viewer. They don't lose access silently, and the
  new owner can remove them.
- The lock and pending requests are unchanged. Approver rights follow the role, so they move to
  the new owner.
- Both owner transfers and super-admin assignments are audited.
Users with no role on a project do not see it: it is absent from lists and direct access
returns 404 (not 403, to avoid leaking existence).

### 2.2 The write lock

- On creation/import the creator holds the lock.
- With no holder, any member (owner or viewer) can **acquire** it directly, no approval.
- The holder can **release** it at any time.
- The owner can **take over** the lock at any time, without approval.
- The lock **expires** after a configurable idle period with no write activity
  (`GLOW_PROJECT_LOCK_IDLE_TIMEOUT`, default 8 h). "Write activity" = any successful write
  request by the holder (section 2.4). Expiry is evaluated lazily whenever the lock is read or
  contended; no background job is required.
- **The lock never moves while a transaction is running on the project** (method status
  running, as tracked today by `verify_project_no_running_methods`). This applies to every
  transfer path: approval, owner takeover, release, super-admin force release, unsharing, and
  expiry (a running transaction also counts as activity, so the lock cannot expire under it).
  The attempt returns 409 with a reason the UI can show ("a transaction is running; try again
  when it finishes"). Rationale: results of a solve started by A must never be written under
  B's lock.
- **Stuck transactions.** In web deployments nothing resets a method left "running" after its runner
  died. Once a running method has exceeded `GLOW_PROJECT_STUCK_METHOD_TIMEOUT` (default 24 h),
  the **owner or a super admin** can mark it **failed** through a dedicated action. That
  unblocks lock transfers, and the action is audited. Before the timeout the running-transaction
  rule is absolute. Marking a method failed doesn't touch its fields or files; downstream
  invalidation follows whatever the framework does today for a failed method.
- All lock transitions are atomic and serialised per project (reuse the existing per-project
  locking pattern: `SELECT … FOR UPDATE` on PostgreSQL, see `_repository/postgresql.py`).

### 2.3 Write-access requests

- A viewer (or owner, if someone else holds the lock and the owner prefers to ask) can create a
  **write request**. At most one pending request per user per project; several users may have
  pending requests simultaneously.
- If nobody holds the lock, requesting is unnecessary: the UI offers "acquire" instead, and the
  API rejects creating a request with 409.
- A pending request can be **approved** or **denied** by the owner or the current holder, and
  **withdrawn** by its requester.
- **Approve** moves the lock to the requester (subject to the running-transaction rule) and the
  previous holder becomes read-only. Other pending requests stay pending, now addressed to the
  new holder (and still the owner).
- When the lock is released, expires, or is taken over, pending requests stay pending; the UI
  tells requesters the lock is now free so they can acquire it.
- Requests are not notified outside the application (no e-mail). Approvers see pending
  requests when they next look at the project or dashboard.

### 2.4 What counts as a write

Writes require the caller to be the current lock holder. Everything else that reads a project
requires membership (owner or viewer).

Writes (lock holder only):
- `POST /projects/{id}/steps/{step}:{method}` (transactions) — `routers/methods.py`
- method-state `PATCH` — `routers/methods.py`
- step `PATCH` — `routers/steps.py`
- instance `POST/PATCH/DELETE` — `routers/instances.py`
- blob `PUT` — `routers/blobs.py`
- project `PATCH` (display name, description) and `POST :upgrade` — `routers/projects.py`
- BDM lock endpoints on a project — `routers/projects.py`
- GraphQL mutation `update_project_steps_with_json` — `routers/graphql.py`
- posting step events — `routers/events.py`

Not covered (decided while writing this design): solution configuration `PUT /solution-configuration`
is server-wide, not per project, so it keeps today's behaviour. MCP is never mounted when
authentication is enabled (`_server/server.py:231`), so it cannot coexist with this feature;
the builder adds a test asserting MCP stays off when access control is enabled, and making MCP
work with auth is out of scope.

Owner-only (or super admin): project `DELETE`, share/unshare, ownership transfer.

Reads (members): project `GET`, `:export`, step/data `GET`, method states, blobs `GET`,
GraphQL queries, event streams (HTTP and WebSocket).

Opening a project in an old schema requires `:upgrade`, which is a write. A viewer who opens such a
project is told that the lock holder (or anyone, if the lock is free) must upgrade it first.

Create/import: any authenticated user; caller becomes owner and holder.

`GET /projects` (and the GraphQL/MCP equivalents) return only projects the caller is a member
of; for a super admin, all projects.

A write without holding the lock returns **423 Locked** with a body containing the current
holder id (or null) so the UI can explain. A non-member gets **404**. A member attempting an
owner-only action gets **403**.

### 2.5 Transactions and internal callbacks

Transactions keep working after they start even though the method runner calls back into the
API with the local `x-api-key` instead of the user's token (`_executor/method_runner.py:323-333`).
The runner must carry the identity of the user who started the transaction on those callbacks
(e.g. an `x-glow-on-behalf-of: <sub>` header that the API honours **only** when a valid API key
is also present), and access checks are evaluated for that user. Because the lock cannot move
while the transaction runs, those writes are always authorised. API-key calls without an
on-behalf-of user (pure framework internals) keep today's behaviour.

### 2.6 Identity and roles — any OIDC provider

- The user id is the standard OIDC `sub` claim of the validated access token. It must be
  extracted on the server for every request (today only the raw token is passed around;
  `saf-iam-oidc` `OidcDependency` returns a string). Introduce a small "current principal"
  (id + roles + is_api_key + on_behalf_of) dependency.
- Role extraction becomes **configurable**: `GLOW_AUTH_ROLES_CLAIM`, a dotted path where
  `{client_id}` is substituted, default `resource_access.{client_id}.roles` (today's Keycloak
  behaviour, so existing deployments are unchanged). Examples: `roles` (Entra ID), `groups`
  (Okta). The existing required/bypass role checks use the same extraction.
- Super admin: `GLOW_AUTH_SUPER_ADMIN_ROLES` (comma-separated, any-of). Empty = no super admin.

### 2.7 Super admin

- Sees every project's metadata in lists: name, dates, owner id, member ids, lock holder,
  orphan flag. "Orphan" = no owner recorded (legacy projects). Projects whose owner left the
  company look normal to GLOW; the UI shows an unresolvable owner as "unknown user", which is
  how a super admin spots them.
- Can assign or reassign the owner of any project, force-release a lock, mark a stuck method
  failed (section 2.2), and delete a project.
- Cannot read steps, fields, files, results, events, or export, and cannot write — unless they
  are also a member (e.g. they assigned themselves as owner, which is audited).
- Every super-admin action, and every ownership change, is recorded in an append-only audit
  table (actor id, action, project id, details, timestamp), readable by super admins through an
  API endpoint.

### 2.8 Existing projects

When the feature is enabled on a database containing projects with no owner, those projects
are orphans: visible to super admins only, until a super admin assigns an owner. Nothing is
migrated automatically.

### 2.9 No names in GLOW

The GLOW API and database store and receive **only user ids** (`sub`). They never store e-mail,
usernames, or display names. Name resolution is the web client's job (section 3). This applies to
every membership backend (2.10), including an external store.

### 2.10 GLOW owns permissions; memberships live in a pluggable backend

Decided 2026-11-27.

- **GLOW is the source of truth** for project permissions, and runs with no App Portal. App Portal
  no longer writes permissions. It reads them from the GLOW API **with the end user's token, through
  the same endpoints and in the same way as the projects dashboard** (`GET /projects`,
  `GET /projects/{id}`, `GET /projects/{id}/access`, `GET /access/me`, and the access actions). There
  is no service-account API and no "ask about another user" endpoint. Because another service now
  depends on it, the access API is a public contract: changes to its paths and response shapes must
  be additive (no removals or renames).
- **App Portal's token is valid for GLOW's client id** (token exchange or a shared client). GLOW's
  authentication (audience check, roles claim, super admin roles) is therefore unchanged by this
  revision.
- **Scope: the GLOW side only.** Today the dependency on App Portal lives outside GLOW: App Portal
  gates on its own OpenFGA before reaching GLOW. Making App Portal stop gating on its own store and
  call GLOW instead is App Portal's work, done outside this plan. Deployment files in this repo are
  not changed either.
- **Two kinds of access state:**
  - **Memberships**: who is the owner and who are the viewers of each project. These are stored by
    the selected *membership backend*.
  - **Everything else**: the write lock, write requests, idle expiry, the change counter that drives
    the live access stream (4.3), and the audit log. These always live in the GLOW database, whatever
    the backend, because they are short-lived, timestamped state that must be serialised with project
    writes (`SELECT … FOR UPDATE`, 2.2).
- Super admin stays a token role (2.6) and is never stored in a backend.
- **Backends:**
  - `database` (default): GLOW's own tables, as already implemented. Nothing extra to install or run.
  - `openfga`: GLOW's **own** OpenFGA store and authorization model, separate from App Portal's.
    GLOW writes and reads the relationships itself. **This iteration ships only the interface and a
    placeholder:** selecting `openfga` fails at startup with a clear
    `"OpenFGA project access backend is not implemented yet"` error, the same way the SCIM and
    Microsoft Graph user directories do (section 3). When it is implemented, its client library ships
    as the optional extra `ansys-saf-glow-engine[openfga]`, and selecting it without the extra fails
    at startup with an error naming the extra. Default installs never pull an OpenFGA dependency.
- **Selection:** `GLOW_PROJECT_ACCESS_BACKEND` = `database` | `openfga`, default `database`. It is
  only read when `GLOW_PROJECT_ACCESS_CONTROL_ENABLED` is `True`.
- **Architecture (dependency injection):** the access rules depend on an abstract membership
  interface, never on the SQL tables. The concrete backend is built once from settings and injected
  through FastAPI's dependency system, like the repository and the user directory. No router, rule,
  DashClient helper, dashboard or banner may know which backend is in use, or branch on it.
- **Same behaviour on every backend:** same rules, status codes and responses. A backend-agnostic
  contract test suite defines that behaviour. It runs against the `database` backend now, and any
  future backend must pass it.
- **What the interface must cover** (exact signatures left to the builder): read the members of one
  project, and of many projects at once (list summaries); add, change the role of, and remove a
  member; give the project ids a user is a member of, and tell which projects have an owner. Those
  last two are what `GET /projects` filtering and `orphans_only` need, with correct totals and
  pagination, once memberships are not in the same SQL database. It must also remove all memberships
  of a deleted project, and carry memberships across `:upgrade` (which today rebuilds the project
  rows under the same id).
- **Failing closed:** an external backend cannot join the GLOW database transaction. The interface
  contract must say in which order the rules apply membership and lock changes, so that a failure
  half-way never leaves anyone with more access than intended. For example, when unsharing the
  holder, the lock is released before the membership is removed. With the `database` backend, both
  stay in one transaction, as today. The live access stream must still fire on membership changes
  whatever the backend, so the rules, not the backend, bump the change counter.
- **Existing App Portal permissions:** projects whose permissions exist only in App Portal's OpenFGA
  are orphans in GLOW (2.8). A super admin reassigns them. Nothing is imported automatically.

## 3. User directory (name ↔ id) — in the Dash UI server

OIDC has no standard way for one user to look up another, so lookups live in the **Dash UI
server** (`glow-engine` `_ui/server.py`, server-side, can hold credentials), not in the GLOW API.

- A pluggable `UserDirectory` interface:
  - `resolve(email_or_username: str) -> user_id | None` — exact match only, no search/prefix.
  - `display_names(user_ids: list[str]) -> dict[user_id, display_name]`.
- Implementations:
  - **Keycloak** (implemented): Keycloak admin REST API, via a dedicated service-account
    client that has only the `view-users` realm-management role. Short-lived in-memory cache
    for display names.
  - **SCIM 2.0, Microsoft Graph, custom**: placeholders only — documented extension point,
    selecting them raises a clear "not implemented" configuration error.
  - **None** (default when unconfigured): `resolve` returns the input unchanged if it looks like
    an id, `display_names` returns ids. The feature still works with raw ids; the UI shows a
    "Copy my user id" action so users can tell an owner their id.
- Configuration (UI server): `GLOW_UI_USER_DIRECTORY` (`none` | `keycloak`), plus Keycloak
  base URL, realm, service-account client id and secret.
- Exposed to the browser as UI-server endpoints (for the React projects dashboard) and to
  Python as DashClient helpers. Callers must be authenticated; results are never persisted.

## 4. UI and developer experience

### 4.1 Projects dashboard (`saf-projects-dashboard`)

- List shows only accessible projects, with **Owner** and **Editing now** columns (names
  resolved via the UI server) and a lock indicator; a badge for pending requests addressed to
  me.
- Context menu by role:
  - Owner: Share… (dialog: add by e-mail/username, list/remove members, transfer ownership),
    Take over lock, Approve/Deny pending requests, Delete.
  - Holder: Release lock, Approve/Deny pending requests.
  - Viewer: Acquire (if free) or Request write access / Withdraw request.
  - Super admin: Assign owner, Force release, Delete; orphan filter.
- Feature disabled → dashboard looks exactly as today.

### 4.2 Inside a solution (Dash)

- `ProjectAccessBanner` component in `dash-super-components`: drop into a layout once. Shows
  "You are editing" / "Read-only — <name> is editing" / "Nobody is editing — Start editing",
  with Request / Withdraw / Release buttons and live Approve/Deny prompts for owner and holder.
  Renders nothing when the feature is disabled.
- DashClient helpers: `get_project_access()` (my role, `can_write`, holder, pending requests),
  `acquire_lock()`, `release_lock()`, `request_write_access()`, `withdraw_request()`,
  `approve_request()`, `deny_request()`, user-directory helpers (`resolve_user`,
  `display_names`), and an access-change event listener so pages can enable/disable their
  inputs.
- The framework does **not** automatically disable arbitrary inputs on solution pages. The
  backend enforces; developers use `can_write` to disable controls, documented with a one-line
  example and applied in the solution template.

### 4.3 Live updates

Access changes (lock acquired/released/expired/taken over, request created/approved/denied/
withdrawn, membership changed) are published as project-level events, so the in-solution banner
updates without polling. The projects dashboard can list many projects at once, so it refreshes
its list every 30 s while visible and right after each action, rather than opening one live
connection per project. (This was decided while writing the plan.) Today's event sources are per step (`EventSource.step_id`);
a project-scoped channel is needed. Subscribing requires membership.

## 5. Enabling it

- `GLOW_PROJECT_ACCESS_CONTROL_ENABLED` (default `False`). Startup fails with a clear error if
  it is `True` while auth is disabled (`GLOW_AUTH_DISABLED=True`).
- Disabled (desktop, auth off, or simply not opted in): zero behaviour change; access endpoints
  return 404; UI components render nothing.
- `GLOW_PROJECT_ACCESS_BACKEND` (default `database`) selects where memberships are stored (2.10).
  An unknown value, or `openfga` in this iteration, makes startup fail with a clear error.

## 6. Goals, non-goals, anti-goals

Goals: private-by-default projects; owner sharing with many viewers; single writer with
request/approve, owner takeover, idle expiry; super admin for orphans; any OIDC provider for
identity and roles; ready-made UI for dashboard and solutions; GLOW as the single authority on
project permissions, usable with no App Portal; memberships stored behind a swappable backend.

Non-goals (this iteration): desktop deployments; sharing with groups/roles; per-step or
per-field permissions; roles other than owner/viewer/holder (e.g. "editor without lock");
e-mail or external notifications; a working OpenFGA membership backend (only its interface
placeholder ships, 2.10); sharing permissions with App Portal's OpenFGA store or importing them;
user-directory adapters other than Keycloak;
automatic orphan detection of departed users.

Anti-goals (would be failures even if it "works"):
- A super admin can silently read project data.
- A running solve ends up writing results under another user's lock, or a lock transfer
  corrupts or loses work in progress.
- GLOW persists names, e-mails or other personal data beyond the `sub` id.
- Any change in behaviour for deployments that do not enable the feature.
- A read path that leaks a project (or its existence) to a non-member, including GraphQL,
  WebSocket events, blobs, MCP, export.
- GLOW needs App Portal (or any service other than its database and the OIDC provider) to enforce
  or store permissions with the default backend.
- Code outside the backend implementations knows or branches on which membership backend is used.
- A backend failure half-way through a change leaves someone with more access than intended.

## 7. Constraints and facts about the current code

- No Alembic; schema evolves via `create_all` + ad-hoc `ALTER TABLE`
  (`_repository/relational.py:1097-1160`). New tables are preferred over altering `projects`.
- Auth env vars are read at import time in `_server/dependencies.py:93-117`; tests that change
  them reload the module.
- Most per-project routers share `dependencies=[Depends(validate_project)]`; the projects
  router does not.
- SQLite and PostgreSQL repositories must both work (tests run on SQLite), even though the
  feature targets PostgreSQL deployments.
- Facts about the implementation on branch `000/bfall/project-access-control`, which the backend
  split has to rework without changing behaviour:
  - Membership reads and writes are methods of the repository session
    (`_repository/relational_access.py`, `RelationalAccessMixin`), alongside the lock, request and
    audit methods. `upsert_member` / `delete_member` also bump the lock row's `version`.
  - `get_access_record` returns members, lock and requests together, and `AccessCrud` decides
    everything from that one record.
  - `list_projects` filters members and orphans with SQL `EXISTS` on `project_members`
    (`_repository/relational.py`), and list summaries join members in SQL.
  - Project deletion and `:upgrade` remove and restore membership rows inside the repository
    (`postgresql.py`, `sqlite.py`, `Crud.upgrade_project`).

## 8. Left to the builder

- Table names and exact schema (suggested shape: members(project_id, user_id, role),
  write_lock(project_id, holder_id, acquired_at, last_write_at), write_requests(id,
  project_id, requester_id, status, timestamps, decided_by), audit(id, project_id, actor_id,
  action, details, at)).
- Viewer UX for old-schema projects that need `:upgrade`.
- Exact REST paths for the access API (follow existing `:{verb}` style, e.g.
  `POST /projects/{id}/lock:acquire`), and the UI-server directory endpoints.
- How the project-scoped event channel is implemented.
- Whether checks are FastAPI dependencies, a `Crud` wrapper, or both — provided every path in
  2.4 is covered and tested, including GraphQL, WebSocket and MCP.
- Cache durations for display names.
- Documentation placement (user guide: deploy/on_premise and backend/authn_authz).
- The membership interface's name, exact methods and module placement; whether the `database`
  backend keeps the current tables as is (expected: yes, no schema change).
- How listing combines backend-provided project ids with SQL filters and pagination for a future
  external backend, provided totals and pages stay correct.
- The OpenFGA authorization model and the settings it will need; this iteration only reserves the
  backend name and the extra. (Builder's call, 2026-11-27: the `[openfga]` extra is not declared in
  `pyproject.toml` yet, since the placeholder needs no dependency. It is documented as reserved.)
