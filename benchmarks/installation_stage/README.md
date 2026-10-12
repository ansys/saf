# SAF installer benchmarks

This directory contains a repeatable Poetry-versus-UV installation benchmark
for the SAF Examples solution.

## Why this benchmark exists

An earlier Windows feasibility investigation evaluated replacing Poetry with UV
during the installer stage. In the PyInstaller virtualized environment, Poetry
was faster: approximately 25-30 seconds offline versus 45-50 seconds for UV,
and 30-35 seconds online versus about 40 seconds for UV.
The recommendation at that time was to keep Poetry for
installer installation, while considering UV for solution development.

The benchmarking confirmed that the original offline local-wheel setup still
makes UV slower, while UV is faster for online installation. Further
investigation showed that UV spent more time installing dependencies referenced
through individual local wheel paths and cleaning up its temporary cache. The
measurements identified where the time was spent, but not the exact internal
cause.

We therefore looked for a better offline dependency layout instead of
abandoning the migration. A wheelhouse groups the dependency wheels in one
directory and lets UV select them through `--find-links`, rather than declaring
each wheel as an individual path. This substantially reduced the installation
and cleanup time in the offline tests.

To ensure that the comparison was not optimized only for UV, we also tested
alternative Poetry configurations. Poetry has no direct equivalent to
`--find-links`, so we evaluated both direct paths to wheels grouped in a
wheelhouse and a locally served HTTP package index. The post-installer
deployment stages remained the same for each comparison.

The benchmark results are:

| Dependency setup | Poetry backend | UV backend | Backend result | Poetry total | UV total | Total result |
|---|---:|---:|---|---:|---:|---|
| Online package sources | 181.0 s | 128.7 s | **UV by 52.2 s (28.9%)** | ~259.2 s | ~207.6 s | **UV by ~51.6 s (19.9%)** |
| Original offline setup | 168.8 s | 215.9 s | **Poetry by 47.1 s (21.8%)** | ~249.6 s | ~301.2 s | **Poetry by ~51.6 s (17.1%)** |
| Poetry original; UV wheelhouse | 153.0 s | 109.8 s | **UV by 43.1 s (28.2%)** | 226.7 s | 188.2 s | **UV by 38.5 s (17.0%)** |
| Poetry local HTTP package index; UV wheelhouse | 151.8 s | 104.8 s | **UV by 47.0 s (31.0%)** | 232.8 s | 190.8 s | **UV by 41.9 s (18.0%)** |
| Poetry wheelhouse paths; UV wheelhouse | 136.5 s | 111.2 s | **UV by 25.3 s (18.5%)** | 214.5 s | 193.1 s | **UV by 21.3 s (9.9%)** |

Backend time covers dependency environment installation and cleanup. Total time
covers payload setup, backend installation, application preload, and shortcut
creation.

UV was faster online, while Poetry was faster with the original offline
direct-path payload. Using a wheelhouse removed UV's offline disadvantage: UV
was faster than every tested Poetry configuration. These results support
migrating the SAF template to UV with the wheelhouse workflow for offline
payloads, rather than directly converting the existing wheel-path layout.
They apply to the tested SAF solution, tool versions, Windows environment, and
benchmark conditions.

## Benchmark design

The benchmark installs the same SAF Examples solution with both backends. Each
case varies:

| Dimension | Values |
|---|---|
| Package availability | Online or offline |
| Installation backend | Poetry or UV |
| Offline source | Standard, direct-path, wheelhouse, or local package server |

Online cases resolve dependencies normally. Offline cases use the wheels staged
by the SAF build, without an external package index. Wheelhouse cases install
from local wheel files. The Poetry server case serves those wheels through a
local PEP 503 index.

Each case gets an isolated workspace and environment under the result
directory. The harness copies the Examples solution, stages its path
dependency, runs `saf install` and `saf build`, and then prepares the payload.
The source SAF repository is not modified.

The report separates payload preparation from timed deployment. Deployment
timings cover backend installation, application preload, shortcut creation, and
their total. Payload copying, wheelhouse or server setup, and lock generation
are reported as preparation time.

## Setup

Run the harness from the SAF repository root:

```powershell
python benchmarks\installation_stage\run_benchmarks.py
```

The harness discovers `uv` on `PATH`. It first looks for the SAF CLI in the
repository's existing Examples environment. If it is unavailable, it creates a
private CLI environment under the benchmark result directory; that fallback
may need network access. Use `config.example.json` when executable paths differ.

Harness-controlled writes remain inside `benchmarks\installation_stage`. An
explicit `--output-dir` must name a directory under that path; relative paths
are resolved relative to the harness directory.

The harness prints progress for source preparation, payload setup, dependency
installation, application preload, and shortcut creation. Detailed command
output remains in each run's log files.

## Commands

Use the double-dash form for all long options. With no selection options, the
harness runs three repetitions of the default matrix:

```powershell
python benchmarks\installation_stage\run_benchmarks.py
```

The default matrix contains three runs for each of:

- online Poetry;
- online UV;
- offline Poetry; and
- offline UV direct-path.

### Select the scope

```powershell
python benchmarks\installation_stage\run_benchmarks.py --online
python benchmarks\installation_stage\run_benchmarks.py --offline
python benchmarks\installation_stage\run_benchmarks.py --online --offline
python benchmarks\installation_stage\run_benchmarks.py --offline --poetry-only
python benchmarks\installation_stage\run_benchmarks.py --offline --uv-only
```

Use `--run N` to set the number of repetitions:

```powershell
python benchmarks\installation_stage\run_benchmarks.py --online --run 5
```

### Select an offline source variant

Without a variant option, offline UV uses direct local wheel paths and offline
Poetry uses its standard offline setup:

```powershell
python benchmarks\installation_stage\run_benchmarks.py --offline --uv-only --uv-wheelhouse --run 3
python benchmarks\installation_stage\run_benchmarks.py --offline --poetry-only --poetry-wheelhouse --run 3
python benchmarks\installation_stage\run_benchmarks.py --offline --poetry-only --poetry-server --run 3
```

The Poetry wheelhouse and server options are mutually exclusive.

### Inspect or control a run

Preview the selected cases without preparing payloads:

```powershell
python benchmarks\installation_stage\run_benchmarks.py --offline --poetry-only --dry-run
```

| Option | Description |
|---|---|
| `--run N` | Repeat each selected case `N` times. |
| `--config PATH` | Use a JSON configuration file. |
| `--output-dir PATH` | Write results under `benchmarks\installation_stage`. |
| `--dry-run` | Print the selected cases without running them. |
| `--fail-fast` | Stop after the first failed case. |

## Implementation notes

The implementation is split into focused modules:

```text
run_benchmarks.py   command-line entry point and run orchestration
prepare.py          source workspaces, SAF builds, and payload preparation
uv_prepare.py       backend-specific projects, wheelhouses, and lock files
deploy.py           one isolated timed Poetry or UV deployment
report.py           Markdown report and averages
```

The UV test payloads contain their own UV-specific `pyproject.toml` and
`uv.lock`. They are not created with `uvx migrate-to-uv`: for online and
direct-path cases, the harness converts the Poetry project produced by `saf
build` and runs `uv lock`; for the wheelhouse case, it creates a minimal UV
project and locks it against the local wheelhouse. The deployment then runs
`uv sync --locked` using those files.
