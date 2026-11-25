# SAF install, build, and launch benchmark

This directory automates a Poetry-versus-UV comparison. It benchmarks three SAF steps only: `saf install`,
`saf build`, and the launch of the generated installer. Other parts of the
solution lifecycle are not measured.

Each step runs on three prepared solutions of increasing size (`small`,
`medium`, `large`). The harness stores logs for every run and writes a Markdown
report with the measured numbers.

The structure follows the sibling `installation_stage` benchmark.

## What is measured

| Mode | Stage | Timed command | Un-timed preparation |
|---|---|---|---|
| `dev` | `install` | `saf install` | Fresh copy of the fixture |
| `dev` | `build` | `saf build` (online) or `saf build --offline-package` (offline) | Copy + `saf install` |
| `prod` | `launch` | `<solution>-installer --no-ui --installation-directory <dir>` | Copy + install + build, or reuse of the installer built in `dev/build` |

Each case varies:

| Option | Values | Default |
|---|---|---|
| `--mode` | `dev`, `prod` | both |
| `--stage` | `install`, `build`, `launch` (narrows `--mode`) | all stages of the selected modes |
| `--os` | `Windows`, `Linux` (Linux runs through WSL on Windows) | current OS |
| `--size` | `small`, `medium`, `large` | all |
| `--backend` | `poetry`, `uv` | both |
| `--network` | `online`, `offline` (build and launch only) | both |
| `--run N` | number of runs per case | 3 |

The fixture sizes are:

| Size | Dependencies |
|---|---|
| `small` | `ansys-saf-sdk` only (template default). |
| `medium` | `small` + pinned binary wheels: `duckdb`, `orjson`, `lz4`, `xxhash`. |
| `large` | `medium` + a private-index package (`ansys-dash-treeview`), a Git dependency (`sampleproject`), and a local wheel (`build_assets/saf_benchmark_local-1.0.0-py3-none-any.whl`). |

The Poetry and UV fixtures declare the same dependencies.

## Setup

1. Install the SAF CLI and make `saf` available on `PATH`, or set
   `saf_executable` in a configuration file. The fixtures require SAF CLI
   4.5 or later: older versions cannot install UV solutions. The report shows
   the SAF CLI version and path used on each OS.
2. For `large`, provide credentials for the private index through the usual
   environment variables (`POETRY_HTTP_BASIC_SOLUTIONS_PRIVATE_PYPI_*` and
   `UV_INDEX_SOLUTIONS_PRIVATE_PYPI_*`). The harness forwards those variables to
   WSL; it never writes them to the fixtures or the logs.
3. For Linux cases from Windows, set up a WSL distribution with Python 3.11+
   and the SAF CLI, then copy `config.example.json` to `config.local.json` and
   adjust the `wsl` section.

`config.local.json` and `config.json` are found automatically beside the
script.

| Key | Description |
|---|---|
| `saf_executable` | SAF CLI for native runs. Default: `saf` on `PATH`. |
| `fixtures_directory` | Fixture root (`<backend>/<size>`). Default: `fixtures`. |
| `work_root` | Scratch workspaces and cached installers for native runs. Default: `.work`. |
| `timeout_seconds` | Per-command timeout; `0` or `null` disables it. Default: 3600. |
| `isolate_caches` | Cold Poetry/UV/pip cache per run. Default: `true`. |
| `forward_environment` | Extra variable names forwarded to WSL. |
| `wsl.distribution` | WSL distribution. Default: the WSL default distribution. |
| `wsl.python`, `wsl.saf_executable` | Python and SAF CLI inside WSL. |
| `wsl.work_root` | Linux-side scratch directory (kept off `/mnt` for realistic I/O). |

## Commands

Run from this directory or with the full path:

```powershell
python benchmarks\poetry_uv\install_build_launch\run_benchmarks.py
```

Without options the default matrix runs on the current OS: 3 runs each of
`dev/install`, `dev/build` (online and offline), and `prod/launch` (online and
offline), for all sizes and both backends: 90 runs. A cold build can take
several minutes, so check the selection with `--dry-run` first.

```powershell
# Preview the default matrix
python run_benchmarks.py --dry-run

# dev install only, small and medium, 5 runs
python run_benchmarks.py --mode dev --stage install --size small medium --run 5

# prod launch for UV offline on Linux (WSL)
python run_benchmarks.py --mode prod --os Linux --backend uv --network offline

# Both operating systems from Windows
python run_benchmarks.py --os Windows Linux --size small
```

| Option | Description |
|---|---|
| `--config PATH` | Use a JSON configuration file. |
| `--output-dir PATH` | Result directory inside this folder. Default: `results/<timestamp>`. |
| `--dry-run` | Print the selected runs without running them. |
| `--fail-fast` | Stop after the first failed run. |
| `--keep-workspace` | Keep each run's `.venv`, `dist`, and installed files. |
| `--warm-cache` | Use the user's package caches instead of a cold cache per run. |
| `--retries N` | Re-run a run up to N times on a fresh workspace after a transient failure (network drop, SAF's PyPI check failing, Windows temp-file lock). Default: 2. |
| `--retry-delay SECONDS` | Wait before each retry, multiplied by the attempt number. Default: 60. |
| `--rerun-failed` | With `--output-dir` of an existing session: re-run only the runs that did not pass, keep their old logs in `previousN/`, and rebuild the report. |

Failed attempts are kept in `attemptN/` inside the run folder, and the report
shows the number of attempts for every run. Other failures (for example a
wrong password or a real build error) are never retried.

```powershell
# After a long session, re-run only what failed (same selection options as the original run)
python run_benchmarks.py --os Windows Linux --output-dir results\full_20261125 --rerun-failed
```

Runs of a case alternate between Poetry and UV (`run1` Poetry, `run1` UV,
`run2` Poetry, and so on) so that drift in machine or network speed affects
both backends equally.

## Results

Each session writes to `results/<timestamp>/`, using the same tree as the
manual benchmark:

```text
results/<timestamp>/
  report.md                              Markdown report
  results.json                           all records and settings
  dev/install/<OS>/<size>/<Backend>/runN/
  dev/build/<OS>/<size>/<network>/<Backend>/runN/
  prod/launch/<OS>/<size>/<network>/<Backend>/runN/
      stage.log        timed command output, each line time-stamped
      preparation.log  un-timed preparation commands
      worker.log       worker console output
      result.json      timings, sizes, tool versions, status
```

The report contains:

- a Poetry versus UV table per stage with mean times and the faster backend;
- statistics per case (mean, standard deviation, min, max, preparation time,
  installer size, environment size);
- the launch phase breakdown (startup/unpacking, deployment + dependency
  installation, preload), based on the durations printed by the installer;
- tool versions per OS, every individual run, and failures with log paths.

To merge results, such as Windows and Linux sessions run separately, copy the
run trees into one directory and regenerate the report:

```powershell
python report.py results\<timestamp>
```

## Notes

- On Windows, start the harness from PowerShell or `cmd`. A Git Bash/MSYS
  shell exports a Unix-style `PATH`, so `saf install` cannot find `uv` or
  start Poetry's helper process.
- Scratch workspaces are deleted after each run unless `--keep-workspace` is
  used; logs and results are always kept.
- `prod/launch` creates the solution shortcut as the real installer does. The
  harness removes the shortcut reported by the installer after each run.
- On Windows, the installer requires WebView2 and Windows long paths enabled.
  Otherwise the `--no-ui` run fails and the reason is in `stage.log`.
- The `large` fixture needs network access for the Git and private-index
  dependencies, including when it builds an offline package.

## Implementation

```text
run_benchmarks.py    command line, matrix, WSL dispatch, result tree
lifecycle_stage.py   one timed stage in a sandboxed workspace (stdlib only)
report.py            Markdown report; can regenerate from a result tree
fixtures/            clean Poetry and UV solutions per size
```
