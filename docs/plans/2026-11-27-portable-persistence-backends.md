# Portable Persistence Backends Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make SAF/GLOW select relational DB and blob (primary + data-repo) backends via a dual Provider SPI and packaging entry points, without changing solution application code.

**Architecture:** Introduce `IRelationalBackend` and `IBlobBackend`, discover them through entry points, resolve by config name at API startup, and inject factories into FastAPI dependencies. Phase 1 ships the SPI with sqlite + filesystem as plugins; later phases add SQL dialects, object-store adapters, and versioned data-repo on blobs.

**Tech Stack:** Python 3.11+, Pydantic Settings, FastAPI DI, SQLAlchemy async, `importlib.metadata.entry_points`, existing `AbstractRepositorySession` / BDM `IStorageScope` / `BdmMultiplexor`.

**Spec:** `docs/specs/2026-11-27-portable-persistence-backends-design.md`

## Global Constraints

- Solution code (`StepModel`, `@transaction`, `EntityHandle`, Dash) must not change.
- Desktop defaults remain `sqlite` + `filesystem` + data-repo `none`.
- Multiplexor prefixes `primary/`, `datarepo/`, `hps/`, `method_asset/` stay stable.
- Extend BDM contracts; do not replace `IStorageScope` / `EntityHandle`.
- No online FS→object migrator in v1 (`.safx` export/import only).
- Minerva PLM rewrite is out of scope; keep as optional data-repo strategy.
- Branch names on `ansys/saf` must match `^[0-9].*`.
- Prefer TDD; commit after each task’s green tests.
- Do not commit secrets; prefer workload identity in object-store adapters.

## Review Focus

- Unknown `GLOW_*_BACKEND` name at startup → fail fast with a message listing known plugin names (not a cryptic KeyError mid-request).
- `GLOW_DATABASE_TYPE=postgresql` without `GLOW_DATABASE_BACKEND` → still resolves to the postgresql plugin (alias) for one release.
- Primary backend `s3` and data-repo backend `none` → multiplexor has no `datarepo` subsidiary; `self.data_repository` raises the existing disabled error, not a partial init crash.
- Re-upload same data-repo path on object store → new immutable version; previous version handle still readable.
- MySQL dialect without row-locking capability → worker/concurrency path uses the sqlite-style single-worker guard, not silent data races.

## File map (planned)

| Path | Responsibility |
|------|----------------|
| `packages/glow-engine/src/ansys/saf/glow/persistence/__init__.py` | Public persistence SPI exports |
| `packages/glow-engine/src/ansys/saf/glow/persistence/spi.py` | `IRelationalBackend`, `IBlobBackend`, config models, capabilities |
| `packages/glow-engine/src/ansys/saf/glow/persistence/registry.py` | Entry-point discovery + resolve-by-name |
| `packages/glow-engine/src/ansys/saf/glow/persistence/relational_backends.py` | Built-in `sqlite` (+ later thin wrappers) |
| `packages/glow-engine/src/ansys/saf/glow/persistence/blob_backends.py` | Built-in `filesystem` blob backend |
| `packages/glow-engine/src/ansys/saf/glow/_config/settings.py` | New backend settings + alias mapping |
| `packages/glow-engine/src/ansys/saf/glow/_config/const.py` | New env constant names |
| `packages/glow-engine/src/ansys/saf/glow/_server/dependencies.py` | DI via registry (remove hardcoded if-chains) |
| `packages/glow-engine/pyproject.toml` | Entry points for built-in backends |
| `packages/saf-persistence-sql/` | New package: postgresql + mysql backends |
| `packages/saf-persistence-object-store/` | New package: s3, minio, azure_blob, gcs |
| `packages/glow-engine/src/ansys/saf/glow/_bdm/versioned_store.py` | Data-repo façade over `IBlobBackend` |
| `packages/glow-engine/tests/unit/persistence/` | Registry, settings, SPI unit tests |
| `packages/glow-engine/tests/conformance/persistence/` | Shared conformance suites |

---

## Phase 1 — SPI, registry, sqlite + filesystem plugins, DI

### Task 1: Persistence SPI protocols and config models

**Files:**
- Create: `packages/glow-engine/src/ansys/saf/glow/persistence/__init__.py`
- Create: `packages/glow-engine/src/ansys/saf/glow/persistence/spi.py`
- Test: `packages/glow-engine/tests/unit/persistence/test_spi.py`

**Interfaces:**
- Consumes: `AbstractRepositorySessionFactory`, `Settings`, `SolutionService`, BDM storage factory types
- Produces: `RelationalCapabilities`, `BlobBackendConfig`, `IRelationalBackend`, `IBlobBackend`

- [ ] **Step 1: Write the failing test**

```python
# packages/glow-engine/tests/unit/persistence/test_spi.py
from ansys.saf.glow.persistence.spi import IRelationalBackend, IBlobBackend, RelationalCapabilities


def test_relational_capabilities_defaults():
    caps = RelationalCapabilities()
    assert caps.supports_row_locking is False
    assert caps.supports_json is True


def test_irelational_backend_is_protocol():
    assert hasattr(IRelationalBackend, "name")
    assert hasattr(IRelationalBackend, "create_session_factory")


def test_iblob_backend_is_protocol():
    assert hasattr(IBlobBackend, "name")
    assert hasattr(IBlobBackend, "create_storage_scope_factory")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `saf execute "pytest packages/glow-engine/tests/unit/persistence/test_spi.py -v"`  
(or from glow-engine venv: `pytest tests/unit/persistence/test_spi.py -v`)  
Expected: FAIL with `ModuleNotFoundError: ansys.saf.glow.persistence`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/glow-engine/src/ansys/saf/glow/persistence/spi.py
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._repository.abstract_repository import AbstractRepositorySessionFactory
from ansys.saf.glow._server.solution import SolutionService


class RelationalCapabilities(BaseModel):
    supports_row_locking: bool = False
    supports_json: bool = True
    max_workers_hint: int | None = None


class BlobBackendConfig(BaseModel):
    """Backend-agnostic bag; unknown keys allowed for plugin-specific options."""

    model_config = {"extra": "allow"}

    root: str | None = None
    bucket: str | None = None
    prefix: str = ""
    region: str | None = None
    endpoint_url: str | None = None


@runtime_checkable
class IRelationalBackend(Protocol):
    name: str

    def validate_settings(self, settings: Settings) -> None: ...

    def create_session_factory(
        self,
        settings: Settings,
        solution_service: SolutionService,
    ) -> AbstractRepositorySessionFactory: ...

    @property
    def capabilities(self) -> RelationalCapabilities: ...


@runtime_checkable
class IBlobBackend(Protocol):
    name: str

    def validate_config(self, config: BlobBackendConfig) -> None: ...

    def create_storage_scope_factory(self, config: BlobBackendConfig) -> Any: ...
```

```python
# packages/glow-engine/src/ansys/saf/glow/persistence/__init__.py
from ansys.saf.glow.persistence.spi import (
    BlobBackendConfig,
    IBlobBackend,
    IRelationalBackend,
    RelationalCapabilities,
)

__all__ = [
    "BlobBackendConfig",
    "IBlobBackend",
    "IRelationalBackend",
    "RelationalCapabilities",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest packages/glow-engine/tests/unit/persistence/test_spi.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/glow-engine/src/ansys/saf/glow/persistence packages/glow-engine/tests/unit/persistence/test_spi.py
git commit -m "feat(glow): add persistence backend SPI protocols"
```

---

### Task 2: Entry-point plugin registry

**Files:**
- Create: `packages/glow-engine/src/ansys/saf/glow/persistence/registry.py`
- Test: `packages/glow-engine/tests/unit/persistence/test_registry.py`

**Interfaces:**
- Consumes: entry point groups `ansys.saf.glow.relational_backends`, `ansys.saf.glow.blob_backends`
- Produces: `PluginRegistry.load()`, `get_relational_backend(name)`, `get_blob_backend(name)`, `list_*_backend_names()`

- [ ] **Step 1: Write the failing test**

```python
# packages/glow-engine/tests/unit/persistence/test_registry.py
import pytest

from ansys.saf.glow.persistence.registry import PluginRegistry
from ansys.saf.glow.persistence.spi import IBlobBackend, IRelationalBackend, RelationalCapabilities


class _FakeRel:
    name = "fake_sql"
    capabilities = RelationalCapabilities(supports_row_locking=True)

    def validate_settings(self, settings):  # noqa: ANN001
        return None

    def create_session_factory(self, settings, solution_service):  # noqa: ANN001
        raise NotImplementedError


class _FakeBlob:
    name = "fake_blob"

    def validate_config(self, config):  # noqa: ANN001
        return None

    def create_storage_scope_factory(self, config):  # noqa: ANN001
        return object()


def test_registry_resolves_injected_backends():
    reg = PluginRegistry(
        relational={"fake_sql": _FakeRel()},
        blob={"fake_blob": _FakeBlob()},
    )
    assert isinstance(reg.get_relational_backend("fake_sql"), IRelationalBackend)
    assert isinstance(reg.get_blob_backend("fake_blob"), IBlobBackend)
    assert "fake_sql" in reg.list_relational_backend_names()


def test_registry_unknown_name_lists_known():
    reg = PluginRegistry(relational={"fake_sql": _FakeRel()}, blob={})
    with pytest.raises(ValueError, match="Unknown relational backend 'nope'.*fake_sql"):
        reg.get_relational_backend("nope")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest packages/glow-engine/tests/unit/persistence/test_registry.py -v`  
Expected: FAIL `ModuleNotFoundError: ...registry`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/glow-engine/src/ansys/saf/glow/persistence/registry.py
from __future__ import annotations

from importlib.metadata import entry_points
from typing import Any

from ansys.saf.glow.persistence.spi import IBlobBackend, IRelationalBackend

RELATIONAL_EP_GROUP = "ansys.saf.glow.relational_backends"
BLOB_EP_GROUP = "ansys.saf.glow.blob_backends"


class PluginRegistry:
    def __init__(
        self,
        relational: dict[str, IRelationalBackend] | None = None,
        blob: dict[str, IBlobBackend] | None = None,
    ) -> None:
        self._relational = dict(relational or {})
        self._blob = dict(blob or {})

    @classmethod
    def load(cls) -> PluginRegistry:
        return cls(
            relational=cls._load_group(RELATIONAL_EP_GROUP),
            blob=cls._load_group(BLOB_EP_GROUP),
        )

    @staticmethod
    def _load_group(group: str) -> dict[str, Any]:
        loaded: dict[str, Any] = {}
        for ep in entry_points().select(group=group):
            backend = ep.load()
            instance = backend() if isinstance(backend, type) else backend
            name = getattr(instance, "name", ep.name)
            loaded[name] = instance
        return loaded

    def list_relational_backend_names(self) -> list[str]:
        return sorted(self._relational)

    def list_blob_backend_names(self) -> list[str]:
        return sorted(self._blob)

    def get_relational_backend(self, name: str) -> IRelationalBackend:
        try:
            return self._relational[name]
        except KeyError as exc:
            known = ", ".join(self.list_relational_backend_names()) or "(none)"
            raise ValueError(f"Unknown relational backend {name!r}. Known: {known}") from exc

    def get_blob_backend(self, name: str) -> IBlobBackend:
        try:
            return self._blob[name]
        except KeyError as exc:
            known = ", ".join(self.list_blob_backend_names()) or "(none)"
            raise ValueError(f"Unknown blob backend {name!r}. Known: {known}") from exc
```

Export `PluginRegistry` from `persistence/__init__.py`.

- [ ] **Step 4: Run tests**

Run: `pytest packages/glow-engine/tests/unit/persistence/test_registry.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/glow-engine/src/ansys/saf/glow/persistence/registry.py packages/glow-engine/src/ansys/saf/glow/persistence/__init__.py packages/glow-engine/tests/unit/persistence/test_registry.py
git commit -m "feat(glow): add persistence plugin registry with fail-fast resolve"
```

---

### Task 3: Built-in sqlite relational + filesystem blob backends + entry points

**Files:**
- Create: `packages/glow-engine/src/ansys/saf/glow/persistence/relational_backends.py`
- Create: `packages/glow-engine/src/ansys/saf/glow/persistence/blob_backends.py`
- Modify: `packages/glow-engine/pyproject.toml` (entry points)
- Test: `packages/glow-engine/tests/unit/persistence/test_builtin_backends.py`

**Interfaces:**
- Consumes: `SqliteSessionFactory`, `create_shared_storage_factory` / shared-volume factory
- Produces: backends named `sqlite`, `filesystem`

- [ ] **Step 1: Write the failing test**

```python
def test_sqlite_backend_name_and_capabilities():
    from ansys.saf.glow.persistence.relational_backends import SqliteBackend

    b = SqliteBackend()
    assert b.name == "sqlite"
    assert b.capabilities.supports_row_locking is False


def test_filesystem_backend_name():
    from ansys.saf.glow.persistence.blob_backends import FilesystemBlobBackend

    assert FilesystemBlobBackend().name == "filesystem"
```

- [ ] **Step 2: Run to verify fail** → then implement wrappers that delegate to existing factories.

```python
# relational_backends.py (sketch)
class SqliteBackend:
    name = "sqlite"

    @property
    def capabilities(self) -> RelationalCapabilities:
        return RelationalCapabilities(supports_row_locking=False, max_workers_hint=1)

    def validate_settings(self, settings: Settings) -> None:
        # reuse existing sqlite location validation paths
        ...

    def create_session_factory(self, settings, solution_service):
        from ansys.saf.glow._repository.sqlite_factory import SqliteSessionFactory
        return SqliteSessionFactory(settings, solution_service)
```

```python
# blob_backends.py (sketch)
class FilesystemBlobBackend:
    name = "filesystem"

    def validate_config(self, config: BlobBackendConfig) -> None:
        if not config.root:
            raise ValueError("filesystem blob backend requires config.root")

    def create_storage_scope_factory(self, config: BlobBackendConfig):
        # wire existing create_shared_storage_factory / SharedFilesystemConfiguration
        # using config.root as ${ROOT}
        ...
```

Add to `packages/glow-engine/pyproject.toml`:

```toml
[project.entry-points."ansys.saf.glow.relational_backends"]
sqlite = "ansys.saf.glow.persistence.relational_backends:SqliteBackend"

[project.entry-points."ansys.saf.glow.blob_backends"]
filesystem = "ansys.saf.glow.persistence.blob_backends:FilesystemBlobBackend"
```

- [ ] **Step 3: Reinstall editable glow-engine so entry points refresh; run unit tests**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(glow): register built-in sqlite and filesystem persistence backends"
```

---

### Task 4: Settings — `GLOW_DATABASE_BACKEND`, BDM primary/datarepo backend fields + alias

**Files:**
- Modify: `packages/glow-engine/src/ansys/saf/glow/_config/const.py`
- Modify: `packages/glow-engine/src/ansys/saf/glow/_config/settings.py`
- Test: `packages/glow-engine/tests/unit/persistence/test_settings_backends.py` (extend `tests/unit/test_config.py` if preferred)

**Interfaces:**
- Produces: `glow_database_backend`, `glow_bdm_primary_backend`, `glow_datarepo_backend`, resolved after alias from `glow_database_type`

- [ ] **Step 1: Failing tests**

```python
def test_database_backend_defaults_to_sqlite(monkeypatch):
    monkeypatch.delenv("GLOW_DATABASE_BACKEND", raising=False)
    monkeypatch.delenv("GLOW_DATABASE_TYPE", raising=False)
    from ansys.saf.glow._config.settings import Settings
    s = Settings()
    assert s.resolved_database_backend == "sqlite"


def test_database_type_alias_maps_to_backend(monkeypatch):
    monkeypatch.setenv("GLOW_DATABASE_TYPE", "postgresql")
    monkeypatch.delenv("GLOW_DATABASE_BACKEND", raising=False)
    from ansys.saf.glow._config.settings import Settings
    s = Settings()
    assert s.resolved_database_backend == "postgresql"


def test_explicit_backend_wins_over_type_alias(monkeypatch):
    monkeypatch.setenv("GLOW_DATABASE_TYPE", "sqlite")
    monkeypatch.setenv("GLOW_DATABASE_BACKEND", "postgresql")
    from ansys.saf.glow._config.settings import Settings
    s = Settings()
    assert s.resolved_database_backend == "postgresql"


def test_bdm_primary_defaults_filesystem(monkeypatch):
    monkeypatch.delenv("GLOW_BDM_PRIMARY_BACKEND", raising=False)
    from ansys.saf.glow._config.settings import Settings
    assert Settings().glow_bdm_primary_backend == "filesystem"


def test_datarepo_backend_defaults_none(monkeypatch):
    monkeypatch.delenv("GLOW_DATAREPO_BACKEND", raising=False)
    from ansys.saf.glow._config.settings import Settings
    assert Settings().glow_datarepo_backend == "none"
```

- [ ] **Step 2: Implement fields + `resolved_database_backend` property**

Add constants:
- `GLOW_DATABASE_BACKEND`
- `GLOW_BDM_PRIMARY_BACKEND`
- `GLOW_DATAREPO_BACKEND`

Keep `glow_database_type` for one release; document deprecation in field description.

- [ ] **Step 3: Run config unit tests → PASS → Commit**

```bash
git commit -m "feat(glow): add pluggable backend settings with database type alias"
```

---

### Task 5: Wire FastAPI DI through the registry

**Files:**
- Modify: `packages/glow-engine/src/ansys/saf/glow/_server/dependencies.py` (`_get_repository`, `get_multiplexor_storage_factory`)
- Test: `packages/glow-engine/tests/unit/persistence/test_dependencies_registry.py` and existing route smoke tests

**Interfaces:**
- Consumes: `PluginRegistry.load()`, `Settings.resolved_database_backend`, `glow_bdm_primary_backend`
- Produces: same `AbstractRepositorySessionFactory` / `SafMultiplexorStorageScopeFactory` types as today

- [ ] **Step 1: Failing test — `_get_repository` uses registry name `sqlite` without importing SqliteSessionFactory in the if-chain**

Prefer a unit test that monkeypatches `PluginRegistry.load` to return a fake backend and asserts `create_session_factory` was called.

- [ ] **Step 2: Replace**

```python
# before
if settings.glow_database_type == DatabaseType.Sqlite:
    return SqliteSessionFactory(...)
elif settings.glow_database_type == DatabaseType.PostgreSql:
    return PostgresqlSessionFactory(...)
```

**with**

```python
registry = PluginRegistry.load()
backend = registry.get_relational_backend(settings.resolved_database_backend)
backend.validate_settings(settings)
return backend.create_session_factory(settings, solution_service)
```

For multiplexor primary: resolve `glow_bdm_primary_backend`, build factory from blob backend config (`root` = project files directory). Keep `with_asset_storage_scope` / `with_hps_storage_scope` as today. For data-repo: if `glow_datarepo_backend == "none"`, skip datarepo subsidiary (Phase 1); else leave a clear `NotImplementedError` or keep existing Minerva/FileSystem path until Phase 3.

- [ ] **Step 3: Run glow-engine unit tests that touch projects/DB**

Run: `pytest packages/glow-engine/tests/unit/routes/test_minimal.py packages/glow-engine/tests/unit/test_config.py packages/glow-engine/tests/unit/persistence -v`  
Expected: PASS (or fix regressions)

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(glow): resolve repository and primary BDM via persistence plugin registry"
```

---

### Task 6: Phase 1 verification gate

- [ ] **Step 1: Desktop smoke** — `saf run` (or glow fixture) with defaults; create project; run one transaction; confirm sqlite DB + filesystem project files.

- [ ] **Step 2: Negative test** — set `GLOW_DATABASE_BACKEND=does_not_exist`; API startup/dependency fails with known-names message.

- [ ] **Step 3: Commit docs note** in glow changelog / env-var docs listing new settings (can be draft until Phase 4).

```bash
git commit -m "test(glow): phase1 persistence plugin smoke and unknown-backend guard"
```

**Phase 1 exit criteria:** defaults unchanged; no hardcoded sqlite/postgres branch in `_get_repository`; entry points discover sqlite + filesystem.

---

## Phase 2 — SQL dialects package + S3/MinIO primary blob

### Task 7: Scaffold `ansys-saf-persistence-sql`

**Files:**
- Create package under `packages/saf-persistence-sql/` (follow sibling package layout: `pyproject.toml`, `src/ansys/saf/persistence/sql/…`)
- Move/wrap existing `PostgresqlSessionFactory` as `PostgreSqlBackend`
- Add `MySqlBackend` skeleton with `RelationalCapabilities(supports_row_locking=True)` once dialect works

**Interfaces:**
- Entry points: `postgresql`, `mysql`
- Depends on `ansys-saf-glow-engine` for SPI + session types

- [ ] **Step 1:** Failing test that `PostgreSqlBackend().name == "postgresql"` and `create_session_factory` returns a factory usable with existing postgres test fixtures.

- [ ] **Step 2:** Implement + register entry points; keep glow-engine re-export or entry-point-only (prefer entry-point-only so glow does not import mysql drivers).

- [ ] **Step 3:** Run existing postgres route tests with `GLOW_DATABASE_BACKEND=postgresql`.

- [ ] **Step 4: Commit** `feat(persistence-sql): add postgresql relational backend plugin`

---

### Task 8: MySQL relational backend + capability gating

**Files:**
- `packages/saf-persistence-sql/src/ansys/saf/persistence/sql/mysql.py`
- Modify worker/concurrency selection in settings/dependencies to read `backend.capabilities`

- [ ] **Step 1:** Conformance test module marked `@pytest.mark.mysql` — project create/get/list/FieldState update.

- [ ] **Step 2:** Implement MySQL async engine URL (`mysql+asyncmy://` or project-standard driver); fix dialect-specific DDL/JSON issues behind capability flags.

- [ ] **Step 3:** If `supports_row_locking` is False, force `max_workers_hint=1` path (Review Focus).

- [ ] **Step 4: Commit** `feat(persistence-sql): add mysql relational backend with capability gates`

---

### Task 9: Scaffold `ansys-saf-persistence-object-store` with S3 + MinIO

**Files:**
- Create `packages/saf-persistence-object-store/`
- Implement shared internal `ObjectStoreClient` protocol (put/get/delete/list)
- `S3BlobBackend` (`name="s3"`), `MinioBlobBackend` (`name="minio"`) implementing `IBlobBackend` → BDM-compatible scope factory

**Critical design note:** Object-store scopes must honor BDM immutability and context isolation (method/product/…). Prefer realizing objects into a local cache directory under the project boundary for `get_cached`, same as shared-volume semantics.

- [ ] **Step 1:** Unit tests with `moto` or MinIO testcontainer: `store` → `get_bytes` round-trip; opaque ids prefixed correctly when wrapped by multiplexor as `primary/…`.

- [ ] **Step 2:** Implement adapters; register entry points.

- [ ] **Step 3:** Integration: set `GLOW_BDM_PRIMARY_BACKEND=s3` (or minio), create project, upload blob field, restart API, download same handle.

- [ ] **Step 4: Commit** `feat(persistence-object-store): add s3 and minio blob backends for primary BDM`

---

### Task 10: Wire primary blob backend selection in multiplexor factory

**Files:**
- Modify `SafMultiplexorStorageScopeFactory` / `dependencies.get_multiplexor_storage_factory` to build primary from `IBlobBackend` when not filesystem
- Build `BlobBackendConfig` from `GLOW_BDM_PRIMARY_*` settings (bucket, prefix, region, endpoint)

- [ ] **Step 1:** Test filesystem still default; s3 selected when env set (mocked backend).

- [ ] **Step 2:** Implement config mapping helper `blob_config_from_settings(settings, namespace="primary"|"datarepo")`.

- [ ] **Step 3: Commit** `feat(glow): select primary BDM storage from blob backend settings`

**Phase 2 exit criteria:** Postgres via plugin; MySQL gated; primary project files on S3/MinIO in CI with emulator.

---

## Phase 3 — Data-repo provenance on blob backends + Azure/GCS

### Task 11: `IVersionedObjectStore` + data-repo semantic layer

**Files:**
- Create: `packages/glow-engine/src/ansys/saf/glow/_bdm/versioned_store.py`
- Modify: `packages/glow-engine/src/ansys/saf/glow/_bdm/datarepo.py` implementations to optionally wrap blob backend
- Test: `packages/glow-engine/tests/unit/persistence/test_versioned_store.py`

**Interfaces:**
- Produces: `upload(handle|bytes, path) -> EntityHandle`, `get_entity_handle(path, version=None)`, `list_versions(path)`
- Layout: `{prefix}/{logical_path}/v/{version_id}` + `{prefix}/{logical_path}/latest`

- [ ] **Step 1: Failing tests**

```python
def test_reupload_creates_new_version(store):
    h1 = store.put_bytes(b"a", path="/Data/p/x.txt")
    h2 = store.put_bytes(b"b", path="/Data/p/x.txt")
    assert h1.entity_id != h2.entity_id
    assert store.get_bytes(store.get_entity_handle("/Data/p/x.txt", version="1")) == b"a"
    assert store.get_bytes(store.get_entity_handle("/Data/p/x.txt")) == b"b"  # latest
```

- [ ] **Step 2: Implement versioned store on top of `IBlobBackend` / object client**

- [ ] **Step 3: Commit** `feat(glow): add versioned object store for data-repo provenance`

---

### Task 12: Pluggable data-repo subsidiary in multiplexor

**Files:**
- Modify `SafMultiplexorStorageScopeFactory.with_datarepo_storage_scope`
- Settings: if `glow_datarepo_backend` in (`s3`,`minio`,`azure_blob`,`gcs`,`filesystem`) use versioned blob strategy; if Minerva type kept via existing `GLOW_DATA_REPOSITORY_TYPE` / strategy selector; if `none`, skip

- [ ] **Step 1:** E2E test from existing `test_data_repository.py` patterns against MinIO: upload twice → two versions; multiplexor prefix `datarepo/`.

- [ ] **Step 2:** Ensure Review Focus case: primary=s3, datarepo=none → no crash.

- [ ] **Step 3: Commit** `feat(glow): back data-repo with pluggable blob backends`

---

### Task 13: Azure Blob + GCS adapters

**Files:**
- `packages/saf-persistence-object-store/.../azure_blob.py`
- `packages/saf-persistence-object-store/.../gcs.py`
- Entry points `azure_blob`, `gcs`
- Tests with emulators or recorded SDKs per package norms

- [ ] **Step 1–4:** TDD round-trip + register + CI optional markers + commit  
  `feat(persistence-object-store): add azure_blob and gcs backends`

**Phase 3 exit criteria:** data-repo versioning works on S3-compatible store; Azure/GCS available as plugins; Minerva path still selectable.

---

## Phase 4 — Conformance suite, SDK extras, docs, deprecations

### Task 14: Published conformance test suites

**Files:**
- Create: `packages/glow-engine/src/ansys/saf/glow/persistence/conformance/` (or `packages/saf-testing` plugin)
- Docs: how third parties run `pytest --pyargs ansys.saf.glow.persistence.conformance --backend=acme_s3`

Suites:
1. Relational: project CRUD, FieldState transitions, migration smoke
2. Blob: store/get/stream, immutability (no overwrite of same opaque id), GC unreferenced
3. Data-repo: version bump, latest pointer, get-by-version

- [ ] **Step 1:** Implement suite as pytest plugins parameterized by backend fixtures.
- [ ] **Step 2:** Run suite against sqlite/filesystem and minio in CI.
- [ ] **Step 3: Commit** `test(glow): add persistence backend conformance suites`

---

### Task 15: SDK meta-package extras + public plugin docs

**Files:**
- Modify `packages/saf-sdk` extras: `persistence-aws`, `persistence-azure`, `persistence-gcp`, `persistence-mysql`
- Docs under SAF user guide: env vars, external plugin walkthrough (spec §8)
- Mark `GLOW_DATABASE_TYPE` deprecated in docs and logs (warning once at startup if used without `GLOW_DATABASE_BACKEND`)

- [ ] **Step 1–3:** Implement extras, docs, deprecation warning → commit  
  `docs: document portable persistence backends and SDK extras`

---

### Task 16: Final verification matrix

- [ ] Desktop default path green (no new env).
- [ ] `postgresql` + `filesystem` green.
- [ ] `postgresql` + `minio` primary + `minio` datarepo green.
- [ ] Unknown backend name fails at startup with known list.
- [ ] Alias `GLOW_DATABASE_TYPE` still works with deprecation warning.
- [ ] Update spec status to `Accepted` when SAF Team signs off (separate docs commit).

```bash
git commit -m "test(glow): persistence portability verification matrix"
```

---

## Spec coverage checklist

| Spec section | Tasks |
|--------------|-------|
| Dual SPI | 1 |
| Entry-point registry / DI | 2, 5 |
| Config + alias | 4 |
| Built-in sqlite/filesystem | 3, 6 |
| First-party SQL package | 7, 8 |
| Object-store package | 9, 10, 13 |
| Data-repo on blobs | 11, 12 |
| External plugin workflow | 14, 15 (docs + conformance) |
| Rollout phases | Phase gates 1–4 |
| Non-goals | Explicitly omitted (no object-only project data, no online migrator, no Minerva rewrite) |

---

## Execution notes

- Prefer implementing **Phase 1 fully** and merging/reviewing before Phase 2 drivers/SDKs land.
- New packages should be added to the monorepo CI job matrix like sibling packages.
- When editing `dependencies.py`, keep websocket and HTTP dependency paths in sync (`get_repository` vs `get_repository_for_websocket`).
