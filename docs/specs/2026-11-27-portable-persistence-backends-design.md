# Portable Persistence Backends for SAF/GLOW

**Date:** 2026-11-27  
**Status:** Awaiting SAF Team review  
**Approach:** Dual Provider SPI + entry-point plugins (hybrid first-party + third-party)

## 1. Intent

SAF solutions must be portable across AWS, Azure, GCP, and on-premises environments without changing solution application code.

### Goals

1. **Relational project data** works with cloud or on-prem SQL services (PostgreSQL, MySQL, and existing SQLite).
2. **Project files (primary BDM)** persist via any blob/object API (filesystem, S3, MinIO, Azure Blob, GCS, …).
3. **Data-repo provenance** uses the same pluggable blob backends (S3, MinIO, …), with versioned path semantics layered on top.
4. Use **abstraction, dependency injection, and packaging entry-point plugins** so Ansys ships a core set and third parties can add backends without forking GLOW.

### Non-goals (v1)

- Moving structured project data out of SQL into object storage.
- Multi-cloud dual-write or automatic cross-provider sync.
- Replacing or rewriting Minerva PLM semantics (Minerva remains an optional data-repo strategy).
- Online migrator from filesystem projects to object storage (export/import `.safx` is the supported path).

### Invariants

- Solution code (`StepModel`, `@transaction`, `EntityHandle`, Dash callbacks) stays unchanged.
- Desktop defaults remain **SQLite + local filesystem BDM + data-repo off**.
- Existing BDM contracts (`EntityHandle`, `IStorageScope` / async variants) remain the blob language; we extend providers, we do not replace the API surface solutions use.
- Multiplexor handle prefixes (`primary/`, `datarepo/`, `hps/`, `method_asset/`) stay stable.

## 2. Current state (baseline)

Today GLOW already has partial seams:

- **Project data:** `AbstractRepositorySession` / `AbstractRepositorySessionFactory` with hardcoded SQLite and PostgreSQL factories in FastAPI dependencies.
- **Project files:** BDM shared-volume filesystem factory; multiplexor routes `primary`, `datarepo`, `hps`, `method_asset`.
- **Data-repo:** optional Minerva or filesystem mock; not a general object-store plugin.
- **Config:** `GLOW_DATABASE_TYPE` enum (`sqlite` | `postgresql`); no public backend SPI.

## 3. Architecture overview

```text
┌─────────────────────────────────────────────────────────────┐
│ Solution (unchanged)                                        │
│  StepModel · @transaction · EntityHandle · FieldState       │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│ GLOW Engine                                                 │
│  AbstractRepositorySession  │  BdmMultiplexor               │
│  (project data + FieldState)│  primary · datarepo · …       │
└─────────────┬──────────────┴──────────────┬─────────────────┘
              │ DI at startup               │
     ┌────────▼────────┐           ┌────────▼────────┐
     │ IRelational     │           │ IBlobBackend    │
     │ Backend         │           │ (shared SPI)    │
     └────────┬────────┘           └────────┬────────┘
              │ entry points                │ entry points
     sqlite│postgres│mysql│…      filesystem│s3│azure│gcs│minio│…
```

Two stable SPIs; one shared blob SPI used for **both** primary BDM and data-repo (different config namespaces + a provenance semantics layer on data-repo).

## 4. Provider SPIs

### 4.1 `IRelationalBackend`

Thin factory over today’s repository abstraction.

| Member | Purpose |
|--------|---------|
| `name: str` | Plugin id, e.g. `sqlite`, `postgresql`, `mysql` |
| `validate_settings(settings)` | Fail fast on bad URI / missing options |
| `create_session_factory(settings, solution_service) -> AbstractRepositorySessionFactory` | Build the session factory |
| `capabilities` (optional) | Row locking, JSON ops, DDL quirks — used by engine guards and tests |

Existing SQLite/Postgres factories become first-party backends. MySQL is a new dialect backend on the same SQLAlchemy models, gated by capability flags and conformance tests.

### 4.2 `IBlobBackend`

Shared by primary project files and data-repo.

| Member | Purpose |
|--------|---------|
| `name: str` | Plugin id, e.g. `filesystem`, `s3`, `azure_blob`, `gcs`, `minio` |
| `validate_config(config)` | Fail fast on missing bucket/endpoint/etc. |
| `create_storage_scope_factory(config)` | Produce BDM-compatible scope/factory implementations |

**Primary** uses the factory for project-file contexts (`method`, `product`, `client`, …) and GC.  
**Data-repo** uses the same SPI under a versioned-path façade (see §6).

### 4.3 Discovery

Packaging entry points (same pattern as SAF CLI `ansys_saf_templates`):

- Group `ansys.saf.glow.relational_backends`
- Group `ansys.saf.glow.blob_backends`

Hardcoded `if DatabaseType…` / filesystem-only construction is replaced by a **plugin registry** resolved once at API startup.

## 5. Configuration and dependency injection

### 5.1 Environment surface

| Variable | Role | Examples |
|----------|------|----------|
| `GLOW_DATABASE_BACKEND` | Relational plugin name | `sqlite`, `postgresql`, `mysql` |
| `GLOW_DATABASE_LOCATION` | Connection URI / path | `postgresql://…`, `mysql+asyncmy://…`, file path |
| `GLOW_BDM_PRIMARY_BACKEND` | Blob plugin for project files | `filesystem`, `s3`, `azure_blob`, `gcs`, `minio` |
| `GLOW_BDM_PRIMARY_*` | Backend-specific primary config | bucket, prefix, region, endpoint, credentials ref |
| `GLOW_DATAREPO_BACKEND` | Blob plugin for data-repo, or `none` | same names as primary; may differ |
| `GLOW_DATAREPO_*` | Data-repo config + upload root | bucket/prefix; keep `GLOW_DATA_REPOSITORY_UPLOAD_ROOT` |

Defaults: `sqlite` + `filesystem` + data-repo `none`.

### 5.2 Startup DI flow

1. Load Pydantic `Settings`.
2. `PluginRegistry` discovers entry points → `name → backend`.
3. Resolve relational + primary blob (+ optional data-repo) by configured names; fail fast if missing or invalid.
4. Build `AbstractRepositorySessionFactory` and primary storage/multiplexor; store on app state.
5. FastAPI dependencies (`get_repository`, BDM helpers) read factories from app state — no dialect `if` chains in `dependencies.py`.

### 5.3 Credentials

Prefer cloud-native identity (IRSA, Managed Identity, Workload Identity) inside the plugin. Secret env vars are a fallback. GLOW core does not import AWS/Azure/GCS SDKs.

### 5.4 Compatibility aliases

Keep `GLOW_DATABASE_TYPE` as a deprecated alias mapping to `GLOW_DATABASE_BACKEND` for one release cycle.

## 6. Data-repo provenance on blob backends

Data-repo is a **semantic layer** over `IBlobBackend`, not a second unrelated storage API.

```text
DataRepository (versioned path API)
        │
        ▼
IVersionedObjectStore  ← thin façade over IBlobBackend
        │
        ▼
IBlobBackend (s3 | minio | azure | gcs | filesystem | …)
```

| Concept | Representation |
|---------|----------------|
| Logical path | e.g. `/Data/<project>/result.dat` |
| Version | Immutable object key / sidecar; `latest` pointer |
| Metadata | JSON sidecar or object user-metadata |
| Handle | `EntityHandle` with `datarepo/` opaque prefix |
| Query | Capability-dependent listing + metadata filter; degrade if unsupported |

Behaviors preserved from today’s `DataRepository` ABC:

- Re-upload same path → new version; return handle to that version.
- `get_entity_handle(path, version=None)` → specific or latest.
- Directory vs blob rules unchanged.
- Multiplexor routes `datarepo/…` without copying into primary unless explicitly pulled.

Primary and data-repo may use the same plugin with different buckets/prefixes, or different plugins entirely.

Minerva remains an optional data-repo **strategy**; S3/MinIO/Azure/GCS/filesystem are the portable blob strategies.

## 7. First-party packages and layout

| Package | Contents |
|---------|----------|
| `ansys-saf-glow-engine` | SPIs, registry, multiplexor, `AbstractRepository*`, built-in **sqlite** + **filesystem** |
| `ansys-bdm-api` | Unchanged BDM contracts |
| `ansys-bdm-shared-volume` | Filesystem `IBlobBackend` (`filesystem`) |
| `ansys-saf-persistence-sql` | **postgresql** + **mysql** relational backends |
| `ansys-saf-persistence-object-store` | **s3**, **minio**, **azure_blob**, **gcs** adapters |

SDK meta-package extras (examples): `persistence-aws`, `persistence-azure`, `persistence-gcp`, `persistence-mysql`.

Illustrative entry points:

```toml
[project.entry-points."ansys.saf.glow.relational_backends"]
postgresql = "ansys.saf.persistence.sql:PostgreSqlBackend"
mysql = "ansys.saf.persistence.sql:MySqlBackend"

[project.entry-points."ansys.saf.glow.blob_backends"]
s3 = "ansys.saf.persistence.object_store:S3BlobBackend"
minio = "ansys.saf.persistence.object_store:MinioBlobBackend"
azure_blob = "ansys.saf.persistence.object_store:AzureBlobBackend"
gcs = "ansys.saf.persistence.object_store:GcsBlobBackend"
```

## 8. External (third-party) plugin workflow

Solution authors do **not** import plugin modules from step or UI code.

### 8.1 Implement

Ship a separate package implementing `IBlobBackend` and/or `IRelationalBackend`, register via entry points, e.g.:

```toml
[project.entry-points."ansys.saf.glow.blob_backends"]
acme_s3 = "acme.saf_persistence.s3_compatible:AcmeS3Backend"
```

Run the published SAF persistence **conformance test suite** before release.

### 8.2 Install

Add the package to the solution environment / deployment image (`pyproject.toml`, `saf execute "pip install …"`, or container layer).

### 8.3 Select at runtime

```bash
GLOW_BDM_PRIMARY_BACKEND=acme_s3
GLOW_BDM_PRIMARY_BUCKET=my-projects
GLOW_DATAREPO_BACKEND=acme_s3
GLOW_DATABASE_BACKEND=postgresql
GLOW_DATABASE_LOCATION=postgresql://...
```

GLOW resolves the name at startup and injects factories. Transactions continue to use `self.storage_scope` / `self.data_repository`.

### 8.4 What external authors must not do

- Change `StepModel` / `@transaction` / Dash code to reference the plugin.
- Fork GLOW to add `elif` backend branches.

## 9. Compatibility, migration, and rollout

### 9.1 Backward compatibility

- Desktop defaults unchanged with zero new config.
- Deprecated `GLOW_DATABASE_TYPE` alias for one release.
- Stable `EntityHandle` and multiplexor prefixes so existing projects load.
- Solution code and BDM call sites unchanged.

### 9.2 Moving a deployment to object storage

1. Provision SQL + bucket/container.
2. Set backend names and identity/credentials.
3. New projects write to the configured backends immediately.
4. Existing projects: export `.safx` → import (supported path). Online FS→object migrator is out of scope for v1.

### 9.3 MySQL

Same relational models; dialect capability flags for locking/JSON/DDL. Conformance tests gate “supported,” not blanket day-one parity with every Postgres edge case.

### 9.4 Phased rollout

| Phase | Deliverable |
|-------|-------------|
| 1 | SPI + registry; sqlite/filesystem as plugins; remove hardcoded if-chains |
| 2 | Postgres/MySQL as `IRelationalBackend`; S3/MinIO as `IBlobBackend` for primary |
| 3 | Data-repo semantic layer on blob backends; Azure/GCS adapters |
| 4 | Public plugin docs + conformance suite; deprecate old env aliases |

## 10. Testing and risks

### 10.1 Testing

- **Unit:** registry resolution, settings validation, alias mapping.
- **Conformance (relational):** project CRUD, FieldState/DAG updates, migrations, concurrent access per capability flags.
- **Conformance (blob):** store/get/stream, immutability expectations, context isolation, GC unreferenced entities, prefix isolation between primary and data-repo.
- **Conformance (data-repo):** version bump on re-upload, latest pointer, get-by-version, multiplexor prefix routing.
- **Integration:** one matrix job per first-party backend (Postgres, MySQL, S3/MinIO via Testcontainers or emulators).
- **Regression:** desktop sqlite+filesystem path remains the default CI smoke.

### 10.2 Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Dialect drift (MySQL vs Postgres) | Capability flags + conformance gates |
| Object-store consistency / eventual reads | Document read-after-write expectations per backend; retries in adapter |
| Credential leakage | Prefer workload identity; no secrets in project data |
| Plugin quality | Mandatory conformance suite for claimed support |
| Config sprawl | Namespaced `GLOW_BDM_PRIMARY_*` / `GLOW_DATAREPO_*`; validate unknown required keys in plugin |
| Large engineering files over WAN | Keep BDM caching/realization semantics; avoid unnecessary cross-space copies |

## 11. Success criteria

- Same solution wheel/source runs on desktop (sqlite+filesystem) and on AWS/Azure/GCP/on-prem by changing **config + installed plugin extras only**.
- Third party can publish an `IBlobBackend` / `IRelationalBackend` package, install it, set `GLOW_*_BACKEND=<name>`, and run without GLOW core changes.
- Primary project files and data-repo provenance both work on S3-compatible and other object stores.
- Existing FieldState / DAG provenance behavior unchanged; data-repo versioning preserved on blob backends.

## 12. Decisions log

| Decision | Choice |
|----------|--------|
| Project files + data-repo on object storage; SQL retained for structured data | Confirmed (option B) |
| Solution code unchanged; desktop defaults; extend BDM not replace | Confirmed |
| Plugin model | Hybrid: Ansys core set + public SPI (option C) |
| Architecture approach | Dual Provider SPI + entry points (Approach 2) |
