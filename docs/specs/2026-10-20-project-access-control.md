# Project Access Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Per-user project ownership, sharing, a single-writer lock with request/approve, and a narrow super-admin role. It lives in the GLOW engine and is exposed through the projects dashboard, DashClient and a drop-in Dash banner.

**Architecture:**
- New GLOW DB tables hold members, the lock, write requests and audit entries. They store user ids only (OIDC `sub`).
- An `AccessCrud` service owns every rule. Two FastAPI dependencies (`require_project_read` / `require_project_write`) and in-lock checks enforce the rules on existing routes. A new `access` router exposes the actions.
- The transaction runner carries the initiating user on its internal API-key callbacks.
- Name ↔ id lookups live only in the Dash UI server, behind a pluggable `UserDirectory`. Keycloak is implemented; the other adapters are placeholders.
- Everything is off unless `GLOW_PROJECT_ACCESS_CONTROL_ENABLED=True`.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy async (SQLite + PostgreSQL), Ariadne GraphQL, Flask/Dash, dash-extensions, dmc, React 19 + TypeScript + Jest (saf-projects-dashboard), pytest.

**Spec:** `docs/superpowers/specs/2026-10-20-project-access-control-design.md`

## Global Constraints

- **Feature flag:**
  - `GLOW_PROJECT_ACCESS_CONTROL_ENABLED` defaults to `False`.
  - When it's off, behaviour must be byte-for-byte unchanged: access routes return 404, `ProjectInfo.access` is `null`, and UI components render nothing.
  - Startup fails if it's `True` while `GLOW_AUTH_DISABLED` is `True`.
- **Ids only:** the GLOW API and DB store and receive only user ids (`sub`), never e-mails, usernames or display names.
- **Status codes:** non-member → 404, write without the lock → 423 (body contains `holder_id`), member doing an owner-only or super-admin action → 403, lock move refused because a transaction is running → 409.
- **Timeouts:**
  - Lock idle timeout: `GLOW_PROJECT_LOCK_IDLE_TIMEOUT`, in seconds, default `28800` (8 h).
  - Stuck-method timeout: `GLOW_PROJECT_STUCK_METHOD_TIMEOUT`, in seconds, default `86400` (24 h).
- **Roles claim:** `GLOW_AUTH_ROLES_CLAIM` is a dotted path, and `{client_id}` in it is replaced by the client id. The default is `resource_access.{client_id}.roles`.
- **Super admin:** `GLOW_AUTH_SUPER_ADMIN_ROLES` is a comma-separated, any-of list. Empty means no super admin.
- **User directory:**
  - `GLOW_UI_USER_DIRECTORY` takes `none` (the default), `keycloak`, `scim` or `msgraph`. The last two raise `NotImplementedError("… user directory is not implemented yet")` at construction.
  - Keycloak settings: `GLOW_UI_KEYCLOAK_URL`, `GLOW_UI_KEYCLOAK_REALM`, `GLOW_UI_KEYCLOAK_CLIENT_ID`, `GLOW_UI_KEYCLOAK_CLIENT_SECRET`.
- **Database:** both SQLite and PostgreSQL repositories must pass. There is no Alembic; add new tables via `Base.metadata.create_all` and new columns via the existing idempotent `ALTER TABLE` helper pattern (`_repository/relational.py:1097`).
- **Python tests:** run from `packages/glow-engine` with `uv run --package ansys-saf-glow-engine --group tests --group tests-glow-engine pytest <path> -v`. Below this is written as `GLOW_PYTEST <path>`.
- **Git state:** before the first commit, the repo's staged-for-deletion index state must be resolved by the user. Do not commit while `git status` shows the whole tree as deleted.
- **Commit style:** `feat(glow-engine): …`, `feat(saf-projects-dashboard): …`, `feat(dash-super-components): …`, `docs: …`.

## Review Focus

1. **Lock moves mid-request.** If the lock moves between a write's permission check and its DB write, the write must still be rejected. Transactions check the lock *inside* `crud.get_modifying_project_lock`, so they're safe (Task 5, `test_transaction_rejected_if_lock_moved_before_prepare`).
2. **Zombie runner.** After the owner marks a stuck method failed and the lock moves, a late callback from the dead runner (`x-glow-on-behalf-of` = old holder) must get 423 and must not write (Task 5, `test_late_callback_from_previous_holder_is_rejected`).
3. **The owner removes the holder.** Unsharing the current lock holder releases the lock, unless a transaction is running, in which case the call returns 409 (Task 4, `test_unshare_holder_releases_lock` and `test_unshare_holder_while_running_conflicts`).
4. **Deleting a project.** Deletion must remove its members, lock, requests and audit rows, or a re-used id would inherit them. Project ids are random, so this is about orphan rows (Task 2, `test_remove_project_deletes_access_rows`).
5. **Tokens without `sub`.** A token with no `sub` claim (some client-credentials tokens) must be treated as unauthenticated for access purposes. It returns 403 on every project route, and it must never match a member row with an empty id (Task 3, `test_token_without_sub_is_rejected`).

---

### Task 1: Settings, configurable roles claim, startup guard

**Files:**
- Modify: `packages/glow-engine/src/ansys/saf/glow/_config/settings.py` (add fields near `glow_auth_disabled` L186)
- Modify: `packages/glow-engine/src/ansys/saf/glow/_utilities/auth_roles.py`
- Modify: `packages/glow-engine/src/ansys/saf/glow/_server/dependencies.py:152-180` (pass the roles claim)
- Modify: `packages/glow-engine/src/ansys/saf/glow/_ui/server.py:170-229` (pass the roles claim)
- Modify: `packages/glow-engine/src/ansys/saf/glow/_server/server.py` (startup guard where the app is built)
- Test: `packages/glow-engine/tests/unit/test_auth_roles.py`, `packages/glow-engine/tests/unit/access/test_settings_guard.py`

**Interfaces:**
- Produces these `Settings` fields:
  - `glow_project_access_control_enabled: bool = False`
  - `glow_project_lock_idle_timeout: int = 28800`
  - `glow_project_stuck_method_timeout: int = 86400`
  - `glow_auth_roles_claim: str = "resource_access.{client_id}.roles"`
  - `glow_auth_super_admin_roles: str = ""`
  - `glow_ui_user_directory: Literal["none", "keycloak", "scim", "msgraph"] = "none"`
  - `glow_ui_keycloak_url: str | None = None`
  - `glow_ui_keycloak_realm: str | None = None`
  - `glow_ui_keycloak_client_id: str | None = None`
  - `glow_ui_keycloak_client_secret: SecretStr | None = None`
  - property `computed_super_admin_roles -> frozenset[str]` (uses `parse_required_roles`)
- Produces in `auth_roles.py`:
  - `get_roles_from_claims(claims: dict[str, Any], roles_claim: str, client_id: str | None) -> set[str]`
  - `has_required_role(claims, client_id, required_roles, bypass_roles=frozenset(), roles_claim: str = DEFAULT_ROLES_CLAIM) -> bool`
  - constant `DEFAULT_ROLES_CLAIM = "resource_access.{client_id}.roles"`
  - `get_client_roles` is kept as a thin wrapper for compatibility.

- [ ] **Step 1: Write failing tests** in `tests/unit/test_auth_roles.py`:

```python
@pytest.mark.parametrize(
    ("claims", "path", "expected"),
    [
        ({"resource_access": {"c": {"roles": ["a", "b"]}}}, "resource_access.{client_id}.roles", {"a", "b"}),
        ({"roles": ["admin"]}, "roles", {"admin"}),
        ({"groups": "g1 g2"}, "groups", {"g1", "g2"}),
        ({"realm_access": {"roles": ["x"]}}, "realm_access.roles", {"x"}),
        ({"roles": ["admin"]}, "missing.path", set()),
        ({"roles": [1, "ok"]}, "roles", {"ok"}),
    ],
)
def test_get_roles_from_claims(claims, path, expected):
    assert get_roles_from_claims(claims, path, "c") == expected

def test_has_required_role_uses_custom_claim():
    assert has_required_role({"roles": ["r"]}, "c", frozenset({"r"}), roles_claim="roles")
```

  And in `tests/unit/access/test_settings_guard.py`:

```python
def test_access_control_requires_auth(settings: Settings):
    settings.glow_project_access_control_enabled = True
    settings.glow_auth_disabled = True
    with pytest.raises(RuntimeError, match="GLOW_PROJECT_ACCESS_CONTROL_ENABLED requires authentication"):
        build_mock_app(settings)
```

- [ ] **Step 2:** Run `GLOW_PYTEST tests/unit/test_auth_roles.py tests/unit/access/test_settings_guard.py`. Expected: FAIL (ImportError / no RuntimeError).
- [ ] **Step 3: Implement.**
  - `get_roles_from_claims`: substitute `{client_id}` (return `set()` if the path needs it and `client_id` is falsy), walk the dicts, and accept either a list of str or a space-separated str.
  - Thread `roles_claim` through:
    - `oidc_scheme_with_api_key` and `oidc_scheme_ws_with_roles`: use `get_settings()` / the injected `settings.glow_auth_roles_claim`.
    - The UI server's `before_request`: use the `settings` passed to `create_app`.
  - Raise the startup `RuntimeError` with exactly that message in the server app factory.
- [ ] **Step 4:** Run the Step 2 tests plus the existing `tests/unit/test_auth_validation.py`. Expected: all PASS.
- [ ] **Step 5:** Commit: `feat(glow-engine): configurable roles claim and project access settings`.

---

### Task 2: Access tables and repository operations

**Files:**
- Modify: `packages/glow-engine/src/ansys/saf/glow/_repository/relational_models.py`. Add the models below and add `started_at` to `MethodState`.
- Create: `packages/glow-engine/src/ansys/saf/glow/_repository/relational_access.py` (`RelationalAccessMixin`).
- Modify: `packages/glow-engine/src/ansys/saf/glow/_repository/abstract_repository.py` (abstract methods).
- Modify: `packages/glow-engine/src/ansys/saf/glow/_repository/relational.py`:
  - Mix into `RelationalSession`.
  - Add `_add_method_states_started_at_column` next to `_add_projects_description_column` and call it at L1157.
  - In `update_method_state`, set `started_at = now(UTC)` when `status` becomes `Running`.
  - Make `list_projects` accept `member_id: str | None = None, orphans_only: bool = False`.
- Modify: `packages/glow-engine/src/ansys/saf/glow/_repository/postgresql.py:109` `remove_project_from_database` and the SQLite equivalent in `_repository/sqlite.py`. Delete the access rows before deleting `Project`.
- Create: `packages/glow-engine/src/ansys/saf/glow/_access/__init__.py` and `_access/schemas.py`.
- Test: `packages/glow-engine/tests/unit/access/test_repository.py`

**Interfaces:**
- Models:
  - `ProjectMember(project_id FK projects.id, user_id String, role Enum(ProjectRole))`, with a unique (project_id, user_id) constraint.
  - `ProjectWriteLock(project_id PK FK, holder_id String|None, acquired_at, last_write_at, version Integer default 0)`.
  - `ProjectWriteRequest(id String uuid PK, project_id FK, requester_id, status Enum(WriteRequestStatus), created_at, decided_by|None, decided_at|None)`.
  - `ProjectAuditEntry(id Integer autoincrement, project_id String (loose, no FK, so it survives deletion), actor_id, action String, details JSON, at DateTime(tz))`.
  - `MethodState.started_at: DateTime(tz) | None`.
- `_access/schemas.py` (pydantic, public via Task 8):
  - `ProjectRole(StrEnum)`: `owner`, `viewer`.
  - `WriteRequestStatus(StrEnum)`: `pending`, `approved`, `denied`, `withdrawn`.
  - `ProjectMemberInfo(user_id: str, role: ProjectRole)`.
  - `WriteRequestInfo(id: str, requester_id: str, status: WriteRequestStatus, created_at: datetime, decided_by: str | None, decided_at: datetime | None)`.
  - `ProjectAccessRecord(project_id: str, members: list[ProjectMemberInfo], holder_id: str | None, acquired_at: datetime | None, last_write_at: datetime | None, version: int, requests: list[WriteRequestInfo])`, which is the raw DB view.
  - `ProjectAccessSummary(owner_id: str | None, holder_id: str | None, my_role: ProjectRole | None, pending_request_count: int)`.
  - `AuditEntryInfo(project_id: str, actor_id: str, action: str, details: dict[str, Any], at: datetime)`.
- Session methods (abstract + relational). Each mutating method also does `version += 1` on the lock row, creating that row if it's missing:
  - `get_access_record(project_id) -> ProjectAccessRecord`
  - `get_access_summaries(project_ids: list[str], user_id: str | None) -> dict[str, ProjectAccessSummary]`
  - `upsert_member(project_id, user_id, role)`, `delete_member(project_id, user_id)`
  - `set_lock_holder(project_id, holder_id: str | None, now: datetime)`, `touch_lock(project_id, now)`
  - `insert_write_request(project_id, requester_id, now) -> WriteRequestInfo`, `set_write_request_status(request_id, status, decided_by, now) -> WriteRequestInfo`
  - `insert_audit_entry(project_id, actor_id, action, details, now)`, `list_audit_entries(project_id: str | None, page: int, page_size: int) -> list[AuditEntryInfo]`
  - `get_running_methods_with_start(project_id) -> list[tuple[str, str, datetime | None]]` returning (step_name, method_name, started_at)
  - `mark_method_failed(project_id, step_name, method_name, message)`

- [ ] **Step 1: Write failing tests** in `tests/unit/access/test_repository.py`, parametrised over SQLite (use the existing `settings` fixture; follow the existing repository tests in `tests/unit` for building a session factory):
  - `test_member_roundtrip`: upsert owner `u1` and viewer `u2`; `get_access_record(...).members == [ProjectMemberInfo("u1", owner), ProjectMemberInfo("u2", viewer)]`.
  - `test_upsert_member_changes_role`: viewer → owner yields a single row.
  - `test_lock_version_increments`: `set_lock_holder` then `touch_lock` gives version `2` and `holder_id == "u1"`.
  - `test_write_request_lifecycle`: insert, then approve, gives `status == approved` and `decided_by == "u1"`.
  - `test_list_projects_filters_by_member`: of 3 projects, `u1` is a member of 2, so `list_projects(..., member_id="u1").total_projects == 2`.
  - `test_list_projects_orphans_only`: a project with no owner row is the only one returned.
  - `test_remove_project_deletes_access_rows`: members, lock and requests are gone; audit rows remain.
  - `test_started_at_set_when_running`: `update_method_state(..., {"status": Running})` sets `started_at`.
- [ ] **Step 2:** Run `GLOW_PYTEST tests/unit/access/test_repository.py`. Expected: FAIL (ImportError).
- [ ] **Step 3:** Implement the models, mixin, column helper, deletion and `list_projects` filter. For the filter, join `ProjectMember` on `member_id`; for orphans, use `~exists(ProjectMember where role == owner)`.
- [ ] **Step 4:** Run Step 2 plus `GLOW_PYTEST tests/unit/routes/test_project.py`. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(glow-engine): project access tables and repository operations`.

---

### Task 3: Principal and on-behalf-of propagation

**Files:**
- Create: `packages/glow-engine/src/ansys/saf/glow/_access/principal.py`
- Modify: `packages/glow-engine/src/ansys/saf/glow/_server/dependencies.py` (add `get_principal`, `get_principal_for_websocket`, `PrincipalDep`, `WSPrincipalDep`; pass `user_id` into the runners at L578-602)
- Modify: `packages/glow-engine/src/ansys/saf/glow/_executor/method_runner.py:90, 323-334, 336`
- Test: `packages/glow-engine/tests/unit/access/test_principal.py`, `packages/glow-engine/tests/unit/test_method_runner.py`
- Create: `packages/glow-engine/tests/unit/access/conftest.py`. It provides the shared fixtures for Tasks 3-6:
  - `make_token(sub: str | None, roles: list[str] = [])`, built like `_make_token` in `test_auth_validation.py:320` with roles under `resource_access["my-client-id"]`.
  - `access_settings`, which enables access control and auth, sets `glow_auth_super_admin_roles="saf_super_admin"`, and patches `oidc_scheme`/`oidc_scheme_ws` `auto_error=True`, `dependencies.audience="my-client-id"` and `validate_access_token` (as `require_app_role` does at L347).
  - `as_user(client, sub, roles=[]) -> dict[str, str]`, which returns headers.

**Interfaces:**
- `ON_BEHALF_OF_HEADER = "x-glow-on-behalf-of"`
- `@dataclass(frozen=True) class Principal: user_id: str | None; is_super_admin: bool; is_internal: bool`
  - `is_internal` is True when authenticated by the local API key.
  - For internal calls, `user_id` comes from `ON_BEHALF_OF_HEADER` (or is None).
- `async def get_principal(request: Request, settings: SettingsDep, token: AccessTokenDep) -> Principal`. It decides internal vs token by comparing `token` with `settings.computed_api_key` via `secrets.compare_digest`. The header is honoured only when the call is internal.
- `MethodRunner.__init__(..., user_id: str | None = None)`, stored as `self._user_id`. `_set_http_auth_headers` / `_set_graphql_auth` add `ON_BEHALF_OF_HEADER: self._user_id` whenever the API key is used and `_user_id` is set. Because it's a plain attribute, it survives pickling into `ProcessMethodRunner`.

- [ ] **Step 1: Write failing tests:**

```python
async def test_principal_from_token(access_settings, make_token): # user_id == "alice", is_super_admin False
async def test_principal_super_admin(access_settings, make_token): # roles ["saf_super_admin"] -> is_super_admin True
async def test_on_behalf_of_ignored_without_api_key(...):  # Bearer + header "x-glow-on-behalf-of: bob" -> user_id "alice"
async def test_on_behalf_of_with_api_key(...):  # api key + header bob -> Principal("bob", False, True)
async def test_token_without_sub_is_rejected(...):  # get_principal -> user_id None, is_internal False
def test_runner_sends_on_behalf_of_header():  # in test_method_runner.py: runner with api key + user_id "alice" -> headers contain both
```

  Test the dependency through a tiny FastAPI app that mounts `get_principal` and returns `dataclasses.asdict(principal)`.
- [ ] **Step 2:** Run `GLOW_PYTEST tests/unit/access/test_principal.py tests/unit/test_method_runner.py`. Expected: FAIL.
- [ ] **Step 3:** Implement as described. `get_method_runner` takes `principal: PrincipalDep` and passes `user_id=principal.user_id`.
- [ ] **Step 4:** Run Step 2 again. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(glow-engine): resolve request principal and propagate initiating user`.

---

### Task 4: AccessCrud — the rules

**Files:**
- Create: `packages/glow-engine/src/ansys/saf/glow/_access/access_crud.py`
- Modify: `_access/schemas.py` (add `ProjectAccess`)
- Modify: `_server/dependencies.py` (`get_access_crud`, `AccessCrudDep`, `WSAccessCrudDep`). These must reuse the same `get_repository` instance as `get_crud` so the nested `get_session` shares one DB session.
- Test: `packages/glow-engine/tests/unit/access/test_access_crud.py`

**Interfaces:**
- `ProjectAccess(project_id: str, owner_id: str | None, members: list[ProjectMemberInfo], holder_id: str | None, lock_acquired_at: datetime | None, last_write_at: datetime | None, version: int, pending_requests: list[WriteRequestInfo], my_role: ProjectRole | None, can_write: bool, is_orphan: bool)`
- `class AccessCrud(session_factory: AbstractRepositorySessionFactory, settings: Settings, now: Callable[[], datetime] = lambda: datetime.now(UTC))`. Every method takes `principal: Principal`.
  - Internal principals with `user_id is None` bypass every check.
  - When `settings.glow_project_access_control_enabled` is False, every `check_*` is a no-op.
  - Mutations run inside `get_session(project_id=…, modification=True, lock_spec=ProjectLockSpecification())`.
- Checks:
  - `check_read(project_id, p) -> None` raises NotFoundError for non-members, except super admin for metadata (see `check_metadata`).
  - `check_metadata(project_id, p)` passes for members and super admins.
  - `check_write(project_id, p, touch: bool = True) -> None`. In order:
    1. Non-member → 404.
    2. Apply expiry.
    3. If the lock is free → `LockedError` with `holder_id=None`.
    4. If the holder isn't `p` → `LockedError(holder_id=…)`.
    5. Otherwise, when `touch`, call `touch_lock`.
  - `check_owner(project_id, p)`: 404 for non-members, 403 for non-owners. Super admin passes only where the spec allows (via the `assign_owner`/`force_release`/`delete` methods).
- Lifecycle and reads:
  - `on_project_created(project_id, p)`: owner + holder = `p.user_id`. No-op if disabled or `p.user_id is None`.
  - `get_access(project_id, p) -> ProjectAccess`, after applying expiry.
- Lock:
  - `acquire(project_id, p)`: lock free (after expiry) → the caller holds it. A held lock → 409 for a viewer, and for the owner too (the owner uses `take_over`).
  - `release(project_id, p)`: holder only, 403 otherwise.
  - `take_over(project_id, p)`: owner only.
  - `force_release(project_id, p)`: super admin only, audited.
- Requests:
  - `create_request(project_id, p) -> WriteRequestInfo`: members; 409 if the lock is free or the caller holds it; 409 if the caller already has a pending request.
  - `withdraw_request(project_id, request_id, p)`: requester only.
  - `approve_request(project_id, request_id, p)`: owner or holder; the lock moves to the requester.
  - `deny_request(project_id, request_id, p)`: owner or holder.
- Members and ownership:
  - `share(project_id, user_id, p)` and `unshare(project_id, user_id, p)`, owner only. Unsharing the holder releases the lock; the owner cannot be unshared.
  - `transfer_ownership(project_id, user_id, p)`: owner only; the target must be a member; the old owner becomes a viewer; audited.
  - `assign_owner(project_id, user_id, p)`: super admin only; the target is added if needed; the old owner (if any) becomes a viewer; audited.
- Super admin and maintenance:
  - `fail_stuck_methods(project_id, p) -> list[str]`: owner or super admin. It marks running methods failed when `started_at is None or now - started_at > stuck timeout`, with the message `"Marked as failed by {user_id}: exceeded stuck-method timeout"`, and is audited. It returns `"step.method"` names.
  - `list_audit(project_id: str | None, page, page_size, p)`: super admin only.
- Shared rules:
  - **Running guard:** every holder change (acquire, release, take_over, force_release, approve, unshare-holder, expiry) first checks `session.get_running_methods(project_id)`. If any are running → `ConflictError("A transaction is running on this project; try again when it finishes.")`.
  - **Expiry:** a held lock expires when `last_write_at + idle_timeout < now` and no method is running. It's evaluated inside each call; when it applies, call `set_lock_holder(None)` and write an audit entry with action `lock_expired`.
- Audit action strings (exact): `ownership_transferred`, `owner_assigned`, `lock_force_released`, `lock_expired`, `methods_failed`.
- `LockedError` responses carry `detail={"message": "...", "holder_id": <id|None>}`.

- [ ] **Step 1: Write failing tests.** Use a fake clock (`now=lambda: clock[0]`) and SQLite. One test per rule, using these names:
  - `test_creator_is_owner_and_holder`
  - `test_non_member_read_is_404`
  - `test_super_admin_metadata_ok_but_read_404`
  - `test_viewer_write_is_423_with_holder`
  - `test_acquire_free_lock`
  - `test_acquire_held_lock_conflicts`
  - `test_release_by_non_holder_403`
  - `test_owner_take_over`
  - `test_take_over_while_running_conflicts`
  - `test_lock_expires_after_idle_timeout` (clock + 28801 s → `holder_id is None`)
  - `test_lock_does_not_expire_while_running`
  - `test_write_touches_last_write_at`
  - `test_request_when_free_conflicts`
  - `test_single_pending_request_per_user`
  - `test_approve_by_holder_moves_lock`
  - `test_approve_by_owner_when_not_holder`
  - `test_viewer_cannot_approve_403`
  - `test_other_requests_stay_pending_after_approve`
  - `test_withdraw_only_by_requester`
  - `test_share_and_unshare_owner_only`
  - `test_cannot_unshare_owner`
  - `test_unshare_holder_releases_lock`
  - `test_unshare_holder_while_running_conflicts`
  - `test_transfer_requires_member`
  - `test_transfer_keeps_old_owner_as_viewer_and_lock`
  - `test_assign_owner_super_admin_only`
  - `test_assign_owner_on_orphan`
  - `test_fail_stuck_methods_respects_timeout` (at 23 h → `[]`; at 24 h + 1 s → `["step.method"]` and status Failed)
  - `test_fail_stuck_methods_null_started_at_is_eligible`
  - `test_force_release_audited`
  - `test_disabled_feature_checks_are_noops`
  - `test_internal_without_user_bypasses`
- [ ] **Step 2:** Run `GLOW_PYTEST tests/unit/access/test_access_crud.py`. Expected: FAIL.
- [ ] **Step 3:** Implement `AccessCrud` and the dependency wiring.
- [ ] **Step 4:** Run Step 2 again. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(glow-engine): project access rules (ownership, sharing, write lock, requests)`.

---

### Task 5: Enforce on existing routes

**Files:**
- Create: `packages/glow-engine/src/ansys/saf/glow/_access/dependencies.py`, providing:
  - `require_project_read(project_id: str, principal: PrincipalDep, access: AccessCrudDep) -> None`
  - `require_project_write(...) -> None`
  - `require_project_owner(...) -> None`
  - `require_project_metadata(...) -> None`
  - WebSocket variants `require_project_read_for_websocket(...)`

  All of them strip the `:verb` suffix from `project_id` (as `dependencies.py:325` does).
- Modify routers:
  - `routers/steps.py`: add `require_project_read` to the router deps at L52; `require_project_write` on PATCH L80.
  - `routers/methods.py`:
    - Router deps: read.
    - `invoke_method`: call `await access.check_write(project_id, principal)` as the **first** statement inside `async with crud.get_modifying_project_lock(project_id)` (L126).
    - `patch_method_state`: `require_project_write`.
  - `routers/instances.py`: router read; write on POST L85, PATCH L126, DELETE L148.
  - `routers/blobs.py`: router read; write on PUT L132.
  - `routers/events.py`: POST store_event write; WS `require_project_read_for_websocket`.
  - `routers/projects.py`:
    - `create_project` / `import_project` call `access.on_project_created`.
    - `list_projects` passes `member_id=principal.user_id` (None for super admin / internal / disabled), plus `orphans_only` from a new `ListProjectRequest.orphans_only: bool = False` (403 if a non-super-admin sets it). It fills `ProjectInfo.access` via `get_access_summaries`.
    - `get_project`: `require_project_metadata`. `:export`: read. PATCH and `:upgrade`: write. DELETE: owner or super admin. bdm-locks: write.
  - `routers/graphql.py`: put `principal` and `access` in `request.scope` and the context. In `resolve_update_project_steps_with_json`, call `check_write` first and map NotFoundError → `NOT_FOUND`, LockedError/ForbiddenError → `PERMISSION_DENIED`.
- Modify: `_server/schemas.py`: `ProjectInfo.access: ProjectAccessSummary | None = None`.
- Test: `packages/glow-engine/tests/unit/access/test_enforcement.py`. Update `EXPECTED_ROUTES` in `tests/unit/test_auth_validation.py` only if routes are added (they aren't in this task).

- [ ] **Step 1: Write failing tests.** Use the `access_settings` fixture with alice as owner/holder, bob shared as viewer, and carol as a stranger:
  - `test_stranger_gets_404_on_every_project_route`: iterate the app's routes containing `{project_id}`, as `_verify_http_routes` does, and assert 404 for carol.
  - `test_viewer_reads_succeed`: step GET, blob GET, method state GET, export.
  - `test_viewer_writes_get_423`: step PATCH, transaction POST, instance POST, blob PUT, events POST, project PATCH, `:upgrade`. Each returns 423 and `detail.holder_id == "alice"`.
  - `test_viewer_graphql_mutation_permission_denied`.
  - `test_delete_owner_only`: bob gets 403, alice gets 200.
  - `test_list_shows_only_member_projects_with_access_summary`.
  - `test_super_admin_lists_all_and_orphans_only`.
  - `test_super_admin_cannot_read_steps_or_export`.
  - `test_transaction_rejected_if_lock_moved_before_prepare`: `mocker.patch.object(Crud, "get_modifying_project_lock")` with an async context manager that first calls `session.set_lock_holder(pid, "bob", now)` and then delegates to the original. alice's transaction POST must return 423 with `holder_id == "bob"`, and no method state may become Running.
  - `test_late_callback_from_previous_holder_is_rejected`: api-key + `x-glow-on-behalf-of: alice` after the lock moved to bob → 423.
  - `test_internal_callback_without_user_allowed`.
  - `test_ws_events_stranger_closed_1008`.
  - `test_feature_disabled_unchanged`: the existing `tests/unit/routes/test_project.py` behaviour with `ProjectInfo.access is None`.
  - `test_mcp_not_mounted_when_access_control_enabled`.
- [ ] **Step 2:** Run `GLOW_PYTEST tests/unit/access/test_enforcement.py`. Expected: FAIL.
- [ ] **Step 3:** Implement the dependencies and router changes above.
- [ ] **Step 4:** Run `GLOW_PYTEST tests/unit/access tests/unit/routes tests/unit/test_auth_validation.py`. Expected: all PASS.
- [ ] **Step 5:** Commit: `feat(glow-engine): enforce project access on REST, GraphQL and event routes`.

---

### Task 6: Access API router and live access stream

**Files:**
- Create: `packages/glow-engine/src/ansys/saf/glow/_server/routers/access.py`
- Modify: `_server/server.py`. Include the router with `global_dependencies` near L151; mount it only when the flag is on, so it returns 404 otherwise.
- Modify: `tests/unit/test_auth_validation.py` `EXPECTED_ROUTES`. The app in those tests has the flag off, so the set is unchanged. Add an assertion that access routes are absent.
- Test: `packages/glow-engine/tests/unit/access/test_access_router.py`

**Interfaces.** Routes and bodies (`UserRef = {"user_id": str}`); every route returns `ProjectAccess` unless noted:
- `GET /access/me` → `{"user_id": str | None, "is_super_admin": bool}`
- `GET /projects/{project_id}/access`
- `POST /projects/{project_id}/access/members` body `UserRef`; `DELETE /projects/{project_id}/access/members/{user_id}`
- `POST /projects/{project_id}/access:transfer-ownership` body `UserRef`; `POST /projects/{project_id}/access:assign-owner` body `UserRef`
- `POST /projects/{project_id}/lock:acquire`, `lock:release`, `lock:take-over`, `lock:force-release`
- `POST /projects/{project_id}/write-requests` → `WriteRequestInfo`; `POST /projects/{project_id}/write-requests/{request_id}:approve`, `:deny`, `:withdraw`
- `POST /projects/{project_id}/methods:fail-stuck` → `{"failed": list[str]}`
- `GET /access/audit?project_id=&page=1&page_size=100` → `list[AuditEntryInfo]`
- `WS /events/projects/{project_id}/access`:
  - Auth works like the existing WS (`oidc_scheme_ws_with_roles`), and the caller must be a member.
  - It sends the `ProjectAccess` JSON immediately, then again whenever `version` changes, checking every `settings.glow_project_access_poll_interval` (new setting, float, default `1.0`).
  - If the caller loses membership, it closes with 1008.

- [ ] **Step 1: Write failing tests**, one per route covering the happy path plus one denial each. For example:

```python
def test_request_approve_flow(client, as_user):
    pid = create_project(client, as_user("alice"))
    client.post(f"/projects/{pid}/access/members", json={"user_id": "bob"}, headers=as_user("alice"))
    r = client.post(f"/projects/{pid}/write-requests", headers=as_user("bob"))
    rid = r.json()["id"]
    a = client.post(f"/projects/{pid}/write-requests/{rid}:approve", headers=as_user("alice")).json()
    assert a["holder_id"] == "bob"
    assert client.get(f"/projects/{pid}/access", headers=as_user("alice")).json()["can_write"] is False
```

  Also cover these:
  - `test_access_routes_404_when_disabled`
  - `test_ws_access_stream_pushes_on_change`: use `TestClient.websocket_connect`; receive the initial message, then acquire/release from another client and receive `version + 1`.
  - `test_ws_access_stream_closes_when_unshared`
- [ ] **Step 2:** Run `GLOW_PYTEST tests/unit/access/test_access_router.py`. Expected: FAIL.
- [ ] **Step 3:** Implement. The routes are thin and delegate to `AccessCrud`.
- [ ] **Step 4:** Run `GLOW_PYTEST tests/unit/access tests/unit/test_auth_validation.py`. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(glow-engine): project access REST API and live access stream`.

---

### Task 7: User directory in the Dash UI server

**Files:**
- Create: `packages/glow-engine/src/ansys/saf/glow/_ui/user_directory.py`
- Modify: `packages/glow-engine/src/ansys/saf/glow/_ui/server.py` `create_app` (L145). Build the directory once, store it with `set_user_directory`, and register the Flask routes on `ui_app.server`. They're protected by the existing `before_request`.
- Test: `packages/glow-engine/tests/unit/access/test_user_directory.py`

**Interfaces:**
- `class UserDirectory(Protocol)`: `def resolve(self, identifier: str) -> str | None`; `def display_names(self, user_ids: Sequence[str]) -> dict[str, str]`.
- `class NoUserDirectory`:
  - `resolve` returns `identifier.strip()` when it's non-empty and contains no `@` and no whitespace; otherwise `None`.
  - `display_names` maps each id to itself.
- `class KeycloakUserDirectory(base_url, realm, client_id, client_secret, cache_ttl_seconds: int = 300)`:
  - Authenticates with the client-credentials grant at `{base_url}/realms/{realm}/protocol/openid-connect/token`.
  - `resolve`: tries `GET /admin/realms/{realm}/users?email={x}&exact=true`, then `?username={x}&exact=true`. If exactly one user matches, it returns `id`; otherwise `None`.
  - `display_names`: `GET /admin/realms/{realm}/users/{id}` per uncached id. The name is `"{firstName} {lastName}".strip()` or `username`; an unknown id (404) is omitted.
  - Uses httpx2 and caches names in memory with the TTL.
- `class ScimUserDirectory` / `class MsGraphUserDirectory`: `__init__` raises `NotImplementedError("SCIM user directory is not implemented yet")` (or `"Microsoft Graph user directory …"`).
- Factory and accessors:
  - `create_user_directory(settings: Settings) -> UserDirectory`. It raises `ValueError` listing any missing Keycloak setting.
  - `get_user_directory() -> UserDirectory` and `set_user_directory(d)` (module-level).
- Flask routes:
  - `GET /_saf/users/resolve?q=<text>` → `{"user_id": str}` or 404.
  - `POST /_saf/users/names` body `{"user_ids": [...]}` (max 200, else 400) → `{"names": {id: name}}`.
  - Responses set `Cache-Control: no-store`.

- [ ] **Step 1: Write failing tests:**
  - Keycloak HTTP mocked with `respx` or `pytest_httpserver` (whichever is already in the `tests-glow-engine` group; check `pyproject.toml`):
    - `test_keycloak_resolve_by_email`
    - `test_keycloak_resolve_falls_back_to_username`
    - `test_keycloak_resolve_ambiguous_returns_none`
    - `test_keycloak_display_names_cached`: the second call makes no HTTP request.
    - `test_keycloak_unknown_id_omitted`
  - Directory selection:
    - `test_no_directory_resolve_rules`
    - `test_placeholders_raise_not_implemented`
    - `test_missing_keycloak_settings_raise`
  - Flask routes (via `create_app(settings).server.test_client()` with auth disabled):
    - `test_flask_routes_resolve_and_names`
    - `test_names_limit_400`
- [ ] **Step 2:** Run `GLOW_PYTEST tests/unit/access/test_user_directory.py`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run Step 2 plus `GLOW_PYTEST tests/unit/test_auth_validation.py -k dash_app`. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(glow-engine): pluggable user directory in the UI server (Keycloak)`.

---

### Task 8: DashClient helpers and public schemas

**Files:**
- Modify: `packages/glow-engine/src/ansys/saf/glow/_client/dashclient.py` (static methods next to `get_deployment_type` L91)
- Modify: `packages/glow-engine/src/ansys/saf/glow/client/__init__.py` (export `ProjectAccess`, `ProjectRole`, `WriteRequestInfo`, `WriteRequestStatus`, `ProjectMemberInfo` and add them to `__all__`)
- Test: `packages/glow-engine/tests/unit/test_dash_client.py`

**Interfaces.** These are static methods on `DashClient`. They call the GLOW API at `os.environ["GLOW_API_URL"]` with the header from `_auth_header_from_ctx()`, raise `httpx2.HTTPStatusError` on errors, and must be called inside a Dash callback:
- `get_project_access(project_id: str) -> ProjectAccess | None`: `None` when the API returns 404 because the feature is disabled. Distinguish this from a missing project by first calling `GET /access/me`: 404 → disabled.
- `acquire_lock(project_id) -> ProjectAccess`, `release_lock(project_id) -> ProjectAccess`, `take_over_lock(project_id) -> ProjectAccess`
- `request_write_access(project_id) -> WriteRequestInfo`, `withdraw_request(project_id, request_id) -> ProjectAccess`, `approve_request(project_id, request_id) -> ProjectAccess`, `deny_request(project_id, request_id) -> ProjectAccess`
- `share_project(project_id, user_id) -> ProjectAccess`, `unshare_project(project_id, user_id) -> ProjectAccess`
- `resolve_user(identifier: str) -> str | None` and `display_names(user_ids: Sequence[str]) -> dict[str, str]`: in-process via `get_user_directory()`.
- `create_access_listener(project_id: str, id: str) -> WebSocket`: same construction as `create_event_listener` (L106), URL `f"{GLOW_WS_EVENTS_ADDR}/events/projects/{project_id}/access"`.

- [ ] **Step 1: Write failing tests**, mocking httpx2 as the existing `test_dash_client.py` does:
  - `test_get_project_access_parses`
  - `test_get_project_access_disabled_returns_none`
  - `test_actions_post_expected_urls` (parametrised over each action → method + URL)
  - `test_auth_header_forwarded`
  - `test_create_access_listener_url_and_protocol`
  - `test_resolve_user_uses_directory`
- [ ] **Step 2:** Run `GLOW_PYTEST tests/unit/test_dash_client.py`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run Step 2 again. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(glow-engine): DashClient project access helpers`.

---

### Task 9: `ProjectAccessBanner` (dash-super-components)

**Files:**
- Create: `packages/dash-super-components/src/ansys/solutions/dash_super_components/project_access_banner.py`
- Modify: the package `__init__.py` (export it)
- Test: `packages/dash-super-components/tests/unit/test_project_access_banner.py`

**Interfaces:**
- `class ProjectAccessBanner(html.Div)`: All-in-One, following `transaction_method_status_badge.py`.
  - Constructor: `__init__(self, project_id: str, aio_id: str | None = None)`.
  - Its layout contains `DashClient.create_access_listener(project_id, id=...)`, a `dmc.Alert` and action buttons.
  - `ansys.saf.glow.client` is imported lazily inside callbacks, because the package doesn't depend on glow-engine.
- Pure render function, tested directly: `render_banner(access: ProjectAccess | None, names: dict[str, str], me: str) -> list[Component]`. Exact copy:
  - `access is None` → `[]` (renders nothing).
  - Holder is me → `"You are editing this project."` with a **Release** button. If I'm the owner or holder and requests are pending: one row per request, `"{name} requests write access"`, with **Approve** / **Deny**.
  - Lock free → `"Nobody is editing this project."` with a **Start editing** button.
  - Someone else holds it → `"Read-only — {holder_name} is editing."` With no pending request of mine: **Request write access**. With one: `"Write access requested"` and **Withdraw**. If I'm the owner: **Take over**.
  - Unknown name → `"unknown user ({id[:8]}…)"`.
- Button callbacks call the matching DashClient method. The WS message re-renders the banner. Developers read `can_write` with `DashClient.get_project_access(project_id).can_write`; document this in the docstring with a one-line example.

- [ ] **Step 1: Write failing tests** for `render_banner`, one per state above (assert the text and the button ids present), plus `test_renders_nothing_when_disabled` and `test_unknown_user_label`.
- [ ] **Step 2:** From `packages/dash-super-components`, run `uv run --package ansys-solutions-dash-super-components --group tests pytest tests/unit/test_project_access_banner.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run Step 2 again. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(dash-super-components): ProjectAccessBanner`.

---

### Task 10: Projects dashboard (React)

**Files:**
- Create: `packages/saf-projects-dashboard/src/ts/api/accessApi.ts`, `src/ts/api/usersApi.ts`, `src/ts/components/ShareDialog.tsx`, `src/ts/components/AccessCells.tsx`
- Modify: `src/ts/components/ProjectsTable.tsx`:
  - Columns after Name: **Owner**, **Editing now**, and a lock icon.
  - Role-based `ContextMenu` items replace the inline items at L94-111.
- Modify: `src/ts/components/ProjectsList.tsx` (same menu items), `src/ts/components/ProjectsDashboard.tsx` (fetch `/access/me`; orphan filter toggle for super admin; 30 s refresh of the list while visible), `src/ts/types` (or wherever `ProjectInfo` is typed: add `access?: ProjectAccessSummary | null`)
- Regenerate the Python wrapper (`npm run build`). New prop: `usersApiBaseUrl` (string, default `""`, relative to the Dash server).
- Test: `src/ts/__tests__/accessApi.test.ts`, `src/ts/__tests__/ProjectsTable.access.test.tsx`, `src/ts/__tests__/ShareDialog.test.tsx`, `tests/unit/test_projects_dashboard_component.py` (prop present)

**Interfaces:**
- `accessApi`: `getMe(baseUrl?)`, `getAccess(projectId, baseUrl?)`, `share(projectId, userId)`, `unshare(projectId, userId)`, `transferOwnership(projectId, userId)`, `assignOwner(projectId, userId)`, `acquire`, `release`, `takeOver`, `forceRelease`, `requestWrite`, `approve(projectId, requestId)`, `deny`, `withdraw`. Same style as `projectsApi.ts` (`buildUrl`, `handleResponse`, `ApiError`).
- `usersApi`: `resolve(text, usersBaseUrl?) -> Promise<string | null>` and `names(ids, usersBaseUrl?) -> Promise<Record<string, string>>`, calling `/_saf/users/*`.
- Menu by role:
  - Owner: Share…, Take over lock (when another user holds it), pending Approve/Deny, Export, Delete.
  - Holder: Release lock, Approve/Deny.
  - Viewer: Start editing (free) / Request write access / Withdraw request.
  - Super admin non-member: Assign owner…, Force release, Delete.
  - Feature off (`project.access == null`): exactly today's items.
- ShareDialog:
  - Input with the label "E-mail or username" and an **Add** button.
  - A resolve failure shows `No user found for "{text}"`.
  - A member list with **Remove** and **Make owner**.
- Unknown names show `unknown user ({id.slice(0, 8)}…)`.
- When `pending_request_count > 0` and I'm the owner or holder, a badge shows the count next to the project name.
- When access control is on, the header has a **Copy my user id** button that copies `getMe().user_id`. This is how users exchange ids when no directory is configured.
- Old-schema projects:
  - When the existing upgrade snackbar would open (`ProjectsDashboard.tsx:485`) for a user without write access, show `This project must be upgraded by the person editing it (or start editing it first).` instead of offering the upgrade.
  - The upgrade call returns 423 in that case.

- [ ] **Step 1: Write failing Jest tests:**
  - `accessApi` URL/method per function.
  - `ProjectsTable` renders Owner/Editing columns only when `access` is present.
  - The menu items per role match the list above exactly (labels).
  - ShareDialog: resolve-then-share flow, and the not-found message.
  - Pending-request badge is shown only to the owner or holder.
  - "Copy my user id" appears only when access control is on.
  - The upgrade snackbar message for a viewer.
- [ ] **Step 2:** In `packages/saf-projects-dashboard`, run `npm test`. Expected: FAIL.
- [ ] **Step 3:** Implement the API modules and components.
- [ ] **Step 4:** Run `npm test`, then `npm run build`, then `uv run --package ansys-saf-projects-dashboard --group tests pytest tests/unit -v` (use the package's actual name from its `pyproject.toml`). Expected: all PASS, and the wrapper has `usersApiBaseUrl`.
- [ ] **Step 5:** Commit: `feat(saf-projects-dashboard): ownership, sharing and write-lock UI`.

---

### Task 11: Templates, docs, end-to-end check

**Files:**
- Modify: the four step templates under `packages/saf-templates/src/ansys/saf/templates/steps/*/…/ui/pages/{{cookiecutter.__ui_page_file_name}}.py`:
  - Add `ProjectAccessBanner(project_id=...)` at the top of the layout.
  - Disable the page's primary action button from a callback on `can_write`.
- Modify: `doc/source/user_guide/backend/authn_authz/authentication.rst` (replace the "no per-project permissions" note at L43 with a link), `doc/source/user_guide/deploy/on_premise.rst` (new env vars and the Keycloak `view-users` service account).
- Create: `doc/source/user_guide/backend/authn_authz/project_access_control.rst`, linked from `index.rst`. It covers roles, lock rules, status codes, settings, DashClient helpers, the banner, and the user directory (with the placeholders noted).
- Create: `packages/glow-engine/tests/e2e/client_server/test_project_access.py`.

- [ ] **Step 1: Write the failing e2e test.** Use the existing e2e auth setup (`tests/e2e/client_server/test_auth_validation.py`, mock IdP `tests/mocks/idp.py`). Extend `get_claims` in the mock IdP so the requested username becomes `sub`, keeping `glow_tests` as the default. The test runs a full scenario:
  1. alice creates and shares with bob.
  2. bob's transaction gets 423.
  3. bob requests, alice approves.
  4. bob's transaction completes (`wait_for_method_completion`) while alice's step PATCH gets 423.
  5. alice takes over after completion.
- [ ] **Step 2:** Run `GLOW_PYTEST tests/e2e/client_server/test_project_access.py`. Expected: FAIL before the IdP tweak, PASS after.
- [ ] **Step 3:** Update the templates and docs. Build the docs with `moon run glow-engine:build-doc` (or the repo's doc task). Expected: no new warnings.
- [ ] **Step 4:** Run the full glow-engine suite: `GLOW_PYTEST tests/unit`. Expected: PASS.
- [ ] **Step 5:** Commit: `docs: project access control; feat(saf-templates): access banner in step templates`.
