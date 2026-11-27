# SAF install, build, and launch benchmark

This directory automates a Poetry-versus-UV comparison. It benchmarks three SAF steps only: `saf install`,
`saf build`, and the launch of the generated installer. Other parts of the
solution lifecycle are not measured.

Each step runs on prepared, minimal but real SAF solutions (one per backend).
Only the `small` size is available for now; larger sizes will be added later.
The size concerns the number of dependencies. The harness stores logs for every
run and writes a Markdown report with the measured numbers.

The structure follows the sibling `installation_stage` benchmark.

## What is measured

| Mode | Stage | Timed command | Un-timed preparation |
|---|---|---|---|
| `dev` | `install` | `saf install` | Solution built from the fixture |
| `dev` | `build` | `saf build` (online) or `saf build --offline-package` (offline) | Copy + `saf install` |
| `prod` | `launch` | `<solution>-installer --no-ui --installation-directory <dir>` | Copy + install + build, or reuse of the installer built in `dev/build` |

Each case varies:

| Option | Values | Default |
|---|---|---|
| `--mode` | `dev`, `prod` | both |
| `--stage` | `install`, `build`, `launch` (narrows `--mode`) | all stages of the selected modes |
| `--os` | `Windows`, `Linux` (Linux runs through WSL on Windows) | current OS |
| `--size` | `small` | all available sizes |
| `--backend` | `poetry`, `uv` | both |
| `--network` | `online`, `offline` (build and launch only) | both |
| `--run N` | number of runs per case | 3 |

## Fixture

Every run uses one shared fixture, so Poetry and UV benchmark the same
solution and only the backend differs:

```text
fixture/
  solution/            README.md and src/ (shared by both backends)
  dependencies.toml    the only list of dependencies
  poetry.lock          committed locks; both pin exactly the same versions
  uv.lock
```

Before each run, `fixture_builder.py` copies `solution/`, writes the Poetry or
UV `pyproject.toml` from `dependencies.toml`, and adds the matching lock file.
The result is a normal SAF solution, so `saf install`, `saf build`, and the
installer run exactly as on a real project. Use
`python fixture_builder.py --write uv <dir>` to look at a generated solution.

The solution is a stripped-down SAF template solution. It keeps only what
`saf install`, `saf build`, and the installer launch need: a one-line
`README.md` (required by Poetry builds) and the Python modules (definition,
steps, `main.py`, UI app and layout page). Documentation, tests, CI files,
deployment files, UI assets, and images are left out, and so are the `tests`
and `style` dependency groups.

`dependencies.toml` keeps three things in mind:

- `ansys-saf-desktop-installer==1.20.0` is pinned directly in the `build`
  group instead of using `ansys-saf-sdk[build]`, which still pins 1.19.0.
- `networkx==3.6` is pinned because Poetry and UV otherwise pick different
  versions on Python 3.12 and later.
- The `doc` group is declared but empty. `saf-desktop-installer` runs
  `poetry export --with desktop,ui,doc` for Poetry offline packages and fails
  when the group does not exist.

| Size | Dependencies |
|---|---|
| `small` | The fixture as is: `ansys-saf-sdk` with the `desktop`, `ui`, and `build` groups (162 packages). |

After editing `dependencies.toml`, update both locks (run from PowerShell or
`cmd`, with `uv` on `PATH`; Poetry runs through `uv tool run`):

```powershell
python fixture_builder.py --relock            # keep current versions where possible
python fixture_builder.py --relock --upgrade  # move to the latest allowed versions
python fixture_builder.py --check             # verify both locks pin the same versions
```

`--relock` only writes the locks when Poetry and UV resolved exactly the same
versions; otherwise it lists the packages to pin in `dependencies.toml`.

## Setup

1. Install the SAF CLI and make `saf` available on `PATH`, or set
   `saf_executable` in a configuration file. The fixture requires SAF CLI
   4.5 or later: older versions cannot install UV solutions. The report shows
   the SAF CLI version and path used on each OS.
2. For Linux cases from Windows, set up a WSL distribution with Python 3.11+
   and the SAF CLI, then copy `config.example.json` to `config.local.json` and
   adjust the `wsl` section.

`config.local.json` is found automatically beside the script (use `-c` for
another file).

| Key | Description |
|---|---|
| `saf_executable` | SAF CLI for native runs. Default: `saf` on `PATH`. |
| `fixture_directory` | Shared fixture folder. Default: `fixture`. |
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
offline), for all sizes and both backends: 30 runs per size. A cold build can
take several minutes, so check the selection with `--dry-run` first.

```powershell
# Preview the default matrix
python run_benchmarks.py --dry-run

# dev install only, 5 runs
python run_benchmarks.py --mode dev --stage install --size small --run 5

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

### Internet connection per run

Every timed step downloads packages (the package caches start empty), so the
connection affects the times. The individual runs table shows, for each run:

| Column | Meaning |
|---|---|
| Download (s) | time the timed command spent receiving data from the internet |
| Download rate (MB/s) | how fast the tool downloaded during that time |
| Internet speed (MB/s) | speed of the connection itself, measured just before the timed command |

**Download rate is not the internet speed.** It depends on the connection *and*
on how the tool downloads: UV fetches many packages at once, while pip (which
installs Poetry before the solution's packages, in `saf install` and at launch)
fetches one file at a time. On the same connection UV therefore usually shows
a higher download rate; that is a real backend difference.

**Internet speed** is measured before every timed command (not timed, about
4 s): the harness downloads the same public file (`plotly-7.2.0`, 9.7 MB, from
`files.pythonhosted.org`) over 4 parallel connections, once to warm up and then
again for about 3 s. It does not depend on the backend, so compare it across
runs and sessions: a slow run with a normal internet speed was slowed by the
tool or the machine, not by the network. If the test fails, the column shows
`-` and the run continues.

The download time and rate come from the machine's network counters, read every
0.25 s while the timed command runs (the downloaded MB is also kept in
`result.json` and `stage.log`). Keep in mind:

- Downloads overlap with unpacking and installing, so the download time is part
  of the stage time, not something to subtract from it.
- The counters cover the whole machine: other downloads running at the same
  time are included.
- On Windows, only physical network cards are counted (filter drivers such as
  QoS, firewall, or VPN layers report the same traffic again). On Linux and WSL,
  every interface except `lo` is counted.

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

## Implementation

```text
run_benchmarks.py    command line, matrix, WSL dispatch, result tree
lifecycle_stage.py   one timed stage in a sandboxed workspace (stdlib only)
report.py            Markdown report; can regenerate from a result tree
network_usage.py     network counters sampled during the timed command (stdlib only)
fixture_builder.py   builds each run's solution from fixture/; --relock, --check, --write
fixture/             shared solution, dependencies.toml, poetry.lock, uv.lock
```
