# Reusing the SAF E2E tests for another solution

This guide explains how to use the examples solution E2E tests as a starting
point for another SAF solution. It is written for a developer who did not
write the original tests and needs to understand what can be copied, what must
be changed, and how to validate the result.

The reference implementation is in this directory:

- [`conftest.py`](./conftest.py) contains the shared lifecycle fixtures and
  helpers.
- [`test_install_dependencies.py`](./test_install_dependencies.py) checks `saf install`
  and the selected locked dependencies.
- [`test_build_installer.py`](./test_build_installer.py) checks `saf build`.
- [`test_execute_installer.py`](./test_execute_installer.py) checks installer
  deployment.
- [`test_execute_shortcut.py`](./test_execute_shortcut.py) checks the
  desktop shortcut and startup.
- [`test_solution_ui.py`](./test_solution_ui.py) checks the browser UI and
  discovers pages dynamically.

The guide describes the behavior of the reference tests. It does not assume
that every solution has the same page names, routes, installer name, API, or
desktop packaging.

## 1. What this suite tests

The tests follow the same path that a user follows:

```text
source solution
      |
      v
  saf install
      |
      v
   saf build
      |
      v
desktop installer
      |
      v
installed solution and desktop shortcut
      |
      v
solution process, API, and UI services
      |
      v
Chrome browser
      |
      v
every page exposed by the solution navigation
```

The acceptance criteria are intentionally split into small tests:

| Behavior | Reference test | What another solution must provide |
|---|---|---|
| Install succeeds | `test_saf_install_completes_successfully` | A working install command and a way to prove the environment was prepared |
| Locked dependencies are installed | `test_saf_install_verifies_locked_dependencies` | A way to inspect the solution environment and compare it with the selected lock-file groups |
| Build creates an installer | `test_saf_build_creates_desktop_installer` | A predictable platform-specific installer artifact |
| Installer deploys files | `test_generated_installer_executes_without_errors` | Installer arguments and a deployed-file marker |
| Shortcut is created | `test_desktop_shortcut_is_created` | The shortcut name and location |
| Shortcut launches the solution | `test_shortcut_launches_solution_and_validates_splash_image` | A launchable shortcut and, on Windows, the expected splash PNG being reported and validated |
| Initial UI loads | `test_solution_ui_is_accessible_in_browser` | A reachable UI and a rendered page-content container |
| All pages render | `test_discovered_pages_render_without_browser_failures` | A rendered navigation tree and a page-content container |

The last row is one pytest item, but it loops over every page discovered at
runtime. A solution with 5 pages and a solution with 50 pages use the same test
code.

## 2. Prerequisites

Install these dependencies in the environment that runs pytest:

| Dependency | Why it is needed |
|---|---|
| Python 3.11 through 3.14 | Runs pytest and the lifecycle helpers; the examples solution currently supports Python 3.11 and 3.12 |
| pytest | Discovers fixtures and test functions |
| Selenium 4 | Controls Chrome and waits for UI state |
| Chrome or Chromium | Renders the solution UI |
| A Selenium-compatible Chrome driver | Connects Selenium to Chrome; Selenium Manager may provide it |
| `psutil` | Finds and terminates the solution process tree |
| `httpx2` | Checks service health and creates a temporary project |
| SAF CLI | Runs `saf install` and `saf build` |

The SAF CLI must be installed in the same environment that runs pytest. The
reference repository uses a local path dependency so its CI tests the current
CLI source:

```toml
ansys-saf-cli = { path = "../packages/saf-cli", develop = true }
```

Do not copy that path dependency into a standalone solution because the
repository does not contain the sibling `packages/saf-cli` directory there.
Install a released CLI version that is compatible with the solution instead.

The reference project declares Selenium directly in
[`pyproject.toml`](../../pyproject.toml). If `psutil` or `httpx2` are only
available transitively in your solution, declare them in the test dependency
group too. Tests should not depend on an unrelated package merely because that
package happens to be installed in one developer's virtual environment.

For the examples solution, run these commands from the `examples` directory to
create the lock file and install the test environment:

```text
saf execute "poetry lock"
saf execute "poetry install --with tests,desktop,ui"
```

The E2E fixture installs the `desktop`, `ui`, and `build` groups separately in
its temporary solution workspace. Do not run that `saf install -f` command in
the checkout where pytest is installed because it can remove the test
environment.

For a new Poetry-based solution, the equivalent dependency command is:

```text
poetry add --group tests ansys-saf-cli pytest selenium psutil httpx2
```

For a non-Poetry project, install the equivalent packages with pip:

```text
python -m pip install ansys-saf-cli pytest selenium psutil httpx2
```

Run `saf --version` to verify that the command is available before starting the
E2E suite. If the CLI is installed in a different environment, set
`SAF_EXECUTABLE` to the full path of its platform-specific executable.

These tests use native Selenium fixtures. They do **not** require
any private package, and the browser options fixture is defined locally in
[`conftest.py`](./conftest.py).

### PIM Light Server in the E2E environment

The examples CI configuration enables `install-pim-light-server`. That step
installs PIM into the Python environment that runs pytest, while the desktop
installer creates a separate virtual environment for the application.

The reference desktop installer and launcher bridge those environments by
adding the runner environment's `site-packages` directory to their
`PYTHONPATH`. The installer preloads the application before creating the
shortcut, so both subprocesses need the extra path. The packaged orchestrator
can then import PIM without adding a private source or a direct PIM dependency
to the solution's `pyproject.toml`. The extra path is not applied to the
`saf install` or `saf build` subprocesses.

Use this only for the E2E runner. It does not place PIM inside the generated
installer, and it is not a substitute for providing PIM through the supported
runtime or packaging mechanism in a user installation.

On Windows, pywin32 needs special handling. Its `pywin32.pth` file adds
`win32`, `win32\lib`, and `Pythonwin` to Python's import path. Python does not
process `.pth` files in a directory that was supplied through `PYTHONPATH`, so
adding only the runner's `site-packages` directory would leave modules such as
`pywintypes` unavailable. The E2E helper forwards the path-only entries from
`pywin32.pth` without executing its `import` line or forwarding unrelated
`.pth` files.

### How CI runs the E2E suite

When a change affects `examples`, the PR workflow adds the examples test matrix
defined in
[`examples.json`](../../../.github/workflows/tests_groups_definitions/examples.json).
The same E2E suite runs on both `windows-latest` and `ubuntu-latest`, so the
desktop lifecycle is checked on both supported operating systems.

For each platform, the reusable
[`_test.yml`](../../../.github/workflows/_test.yml) workflow:

1. Checks out the repository and uses `examples` as the working directory.
2. Creates the Poetry environment with the `tests`, `desktop`, and `ui` groups
   and all project extras.
3. Installs the optional CI services and Linux desktop tools requested by the
   matrix.
4. Runs pytest, which invokes `saf install`, `saf build`, the generated
   installer, the desktop shortcut, and the browser checks.
5. Publishes the pytest report and logs as workflow artifacts.

This keeps the CI check close to a real user journey while giving every
platform a clean runner and an isolated temporary test environment. The
examples code-style job is separate; it does not replace these runtime E2E
checks.

### Additional Linux prerequisites

The desktop shortcut path uses:

- `gtk-launch` to start the `.desktop` entry.
- `xvfb-run` to provide a virtual display for headless execution.

The reference tests fail early with installation guidance when either command
is missing. If the solution has a different Linux launch mechanism, replace
the Linux branch of `LaunchedSolutionProcess` instead of silently skipping
the launch step.

## 3. Copy the reference structure

Create a `tests/e2e` directory in the solution being tested and copy the
reference files into it. Then choose one of these approaches:

### Copy the complete lifecycle

Copy `conftest.py`, all five test modules, and the package marker files
`tests/__init__.py` and `tests/e2e/__init__.py`. This is appropriate when the
solution uses the standard SAF install/build/desktop lifecycle and exposes a
project UI. The package marker files make imports such as
`tests.e2e.conftest` work even when no optional pytest path plugin is installed.

### Copy only the parts that apply

Keep only the fixtures and tests that match the solution. For example:

- A library or server-only solution may keep install, build, and API tests but
  not desktop-shortcut tests.
- A solution without a project API can keep the browser driver and replace
  `_create_project` with the solution's UI entry-point setup.
- A solution with no grouped navigation can keep page discovery and omit the
  group-expansion details.

If you place the tests somewhere other than `tests/e2e`, either keep the
package markers in the matching locations or update the imports in the test
modules to match the new package path.

Do not leave a test in place just because it was copied. Every assertion should
represent a behavior that the solution promises.

## 4. Rename the solution-specific parts first

The test architecture is reusable, but the reference names and artifact
locations belong to the examples solution. Update these before running the
tests:

| Reference value | Location | Replace with |
|---|---|---|
| `EXAMPLES_ROOT` | `conftest.py` | The root of the solution under test |
| `SOLUTION_DISPLAY_NAME` | `conftest.py` | The display name used by the installer and shortcut |
| `InstalledExamples`, `BuiltExamples`, and related names | `conftest.py` and test imports | Optional clearer names for your solution |
| `solution-examples-installer` | `_get_installer_path` | The actual installer basename |
| `Examples E2E` | `_create_project` | A unique name for temporary test projects |
| `examples_workspace` and related fixture names | `conftest.py` and tests | Optional; pytest behavior does not depend on the word `examples` |

The names of pytest fixtures must match their use in test function parameters.
If you rename `running_examples` to `running_solution`, update every test that
requests it.

### Protect the user's environment

The reference [`examples_test_environment`](./conftest.py) fixture redirects
SAF state to temporary directories by setting `APPDATA`, `LOCALAPPDATA`, `HOME`,
`PUBLIC`, `USERPROFILE`, and the XDG directories. Keep this isolation. Add
solution-specific configuration variables when the application stores state in
another location, and restore every original value in fixture teardown.

### The temporary workspace

The reference [`examples_workspace`](./conftest.py) fixture copies the source
solution into a temporary directory and excludes virtual environments, caches,
build output, installers, and the test directory. This protects the checkout
from `saf install` and `saf build`.

For another solution, check the ignore list:

- Keep generated directories out of the copy.
- Keep tests out if the build command should not package them.
- Add solution-specific generated directories if necessary.
- Do not exclude source files required by the build.

If the solution already provides a clean-workspace helper, use that helper
instead of duplicating the copy logic.

## 5. Adapt the install, build, and installer commands

The fixture chain is the most important part of the design:

```text
test environment
    -> solution workspace
    -> installed workspace
    -> built installer
    -> installed desktop solution
    -> launched process
    -> running API and UI
    -> browser
```

Each fixture prepares one state and passes a typed dataclass to the next state.
This makes failures easier to locate: an install failure should occur before
browser setup begins.

### Install

The reference fixture runs:

```text
saf install -f -d desktop,ui,build
```

The groups are defined once in `conftest.py`. The install fixture passes them
to SAF and stores them in `InstalledExamples`; the dependency test reuses that
stored list for Poetry's `--only` filter. This keeps the command under test and
the dependency assertion connected.

The [`saf_executable`](./conftest.py) fixture first checks
`SAF_EXECUTABLE` and then searches for `saf` on `PATH`. Set the
environment variable when the solution must use a repository checkout or a
particular CLI executable.

Change this when the solution needs different arguments or a different CLI
entry point. Keep command output captured and fail with that output when the
command returns a nonzero exit code.

The reference install test checks for:

- Exit code `0`.
- A created virtual environment.
- A generated lock file.

Replace those file checks with artifacts that prove your solution was actually
prepared. Do not assert a filename that your solution does not generate.

### Build

The reference fixture runs:

```text
saf build
```

Update `_get_installer_path` for the actual artifact:

- Windows commonly uses an `.exe`.
- Linux commonly uses an executable without an extension.
- Some solutions use a different output directory or filename.

The build test should check that the command succeeded, the artifact exists,
and the artifact is non-empty. On Linux, also check executable permissions when
the artifact is launched directly.

### Installer execution

The reference installer is run with:

```text
<installer> --no-ui --installation-directory <temporary-directory>
```

Change these arguments to match the installer contract. Always install into a
temporary directory. Never let an E2E test overwrite a developer's normal
installation.

The reference test looks for `version.txt` as proof that deployment wrote
application files. Use a different stable marker if your installer produces
one, for example:

- A known executable.
- A package manifest.
- A version file.
- A required application directory.

Checking only the installer exit code can miss an installer that exits normally
without deploying the application.

## 6. Adapt desktop shortcut launching

`LaunchedSolutionProcess` hides the platform-specific launch details:

- Windows starts the `.lnk` file through `cmd /c`.
- Linux copies the `.desktop` file into the isolated applications directory
  and starts it with `gtk-launch` under `xvfb-run`.
- `psutil` is used to terminate the launcher and its recursive child
  processes during teardown.

Reuse this class when the solution uses standard desktop shortcuts. Change it
when the solution:

- Uses a different shortcut type.
- Requires arguments that are not stored in the shortcut.
- Starts through a custom launcher.
- Creates child processes that need special shutdown handling.

The `stop` path is not optional. A test run that leaves the solution process
alive can affect later tests, retain ports, and make CI jobs unreliable.

### Shortcut checks

Update `_get_shortcut_path` for the actual display name and platform suffix:

- Windows: usually `<name>.lnk`.
- Linux: usually `<name>.desktop`.

Keep the shortcut test separate from the splash test. That way a missing file
and a slow application startup produce different failures.

### Splash checks

The reference fixture waits for the orchestrator log entry that reports the
resolved splash image path. This image signal is the splash check; the test
does not treat the existence of a multiprocessing child process as proof that
an image appeared. The shortcut test verifies that the selected file exists,
has a PNG signature, and is the solution's
`ui/assets/orchestrator/splash.png` when present. If no custom file exists, it
expects the built-in orchestrator image at
`ansys/saf/desktop/orchestrator/_assets/splash.png`.

The fixture waits up to 60 seconds for the image signal. If the signal does not
arrive, the fixture fails before the image assertions run. The image checks are
performed before any later checks so their diagnostics remain visible.

This path check follows the same file that the splash HTML embeds, so it tests
the asset selected for display without adding GUI screenshot dependencies. If a
repository checkout contains the orchestrator source asset, the reference test
also compares the selected default image bytes with that source file. If a
platform does not show a splash screen, skip only the splash assertion for that
platform and continue testing whether the application launches.

## 7. Adapt service discovery and project setup

The running-solution fixture needs two pieces of information:

1. The API URL.
2. The UI URL.

The reference solution writes messages like these to process output or Glow
logs:

```text
Solution API: http://127.0.0.1:<port>/docs
Solution UI: http://127.0.0.1:<port>
```

`_find_solution_log_url` polls both process output and log files because a
Windows GUI process may not expose useful standard output. Update the regular
expressions in `running_examples` when the solution uses different log text or
URL formats.

Then verify the service in stages:

1. Find the API URL.
2. Wait for an HTTP 200 response.
3. Find the UI URL.
4. Create or locate a temporary project.
5. Build the project URL.
6. Wait for the project UI to return HTTP 200.

### Project API assumptions

The reference `_create_project` assumes:

```text
POST <api-base>/projects
JSON body: {"display_name": "..."}
response: {"name": "projects/<id>"}
```

This is a solution contract, not a Selenium requirement. Adapt or replace it
when your solution:

- Uses another endpoint.
- Requires authentication or additional request fields.
- Returns a project ID in another JSON property.
- Does not have projects at all.

If there is no project concept, make `RunningExamples.project_ui_url` point to
the stable UI entry point, or introduce a solution-specific fixture that
creates the state required by the browser test.

## 8. Keep browser testing dynamic

The reference browser test does not contain a list such as:

```python
["/model", "/compute", "/report"]
```

Instead, [`discover_navigation_pages`](./conftest.py) loads the project page,
opens collapsed navigation groups, and reads the visible leaf links. It stores
each page's:

1. Visible label, for readable failure messages.
2. Stable navigation index, when the DOM provides one.
3. `href`, when available.
4. Visible leaf position as a last-resort fallback.

[`navigate_to_discovered_page`](./conftest.py) then finds the page again through
the live navigation tree, clicks it, and waits for at least one valid
navigation signal:

- The browser route changed.
- The page content changed.
- The navigation item became active.

It finally waits for rendered page content before collecting diagnostics.

### What must remain stable

The reference implementation uses these standard SAF layout selectors:

```text
#navbar-content
#page-content
```

These selectors identify the shared layout containers, not examples-specific
pages. Keep them when the solution uses the standard SAF layout. Change the
constants at the top of `conftest.py` when the solution uses different
containers.

The navigation helpers also recognize the standard tree expander and group
indicator elements. If the solution uses a different navigation component,
adapt:

- `NAVIGATION_LINK_SELECTOR`
- `NAVIGATION_EXPANDER_SELECTOR`
- `NAVIGATION_GROUP_INDICATOR_SELECTOR`
- `_is_navigation_group`
- `_is_navigation_group_expanded`

Do not replace this with a hardcoded page list unless dynamic discovery is
impossible. If the component can expose a stable DOM identifier, prefer that
identifier over a label or position.

### What the page smoke test proves

The dynamic test proves that every visible navigation page can be opened and
rendered without:

- A browser console error at `ERROR` or `SEVERE` level.
- An HTTP response with status `400` or higher.
- A `Network.loadingFailed` event.

Expected browser-cancelled navigation requests are ignored when Chrome reports
`net::ERR_ABORTED`. Other `Network.loadingFailed` events remain page failures.

It does not prove that every button, form, table action, upload, or business
workflow works. Add separate behavior tests for those features. The dynamic
page smoke test is a coverage guard, not a replacement for functional tests.

### Waiting correctly

Use explicit waits for UI state. The reference driver uses an implicit wait of
zero because page discovery performs many optional element lookups; combining
implicit and explicit waits can multiply delays. Avoid fixed sleeps such as
`time.sleep(10)` unless a real external timing contract requires one.

When a navigation component replaces DOM nodes during a callback:

- Locate the element again inside the wait callback.
- Ignore stale-element errors while the tree is being updated.
- Retry short-lived click interception or non-interactable errors.

## 9. Use the browser diagnostics correctly

The browser fixture enables Chrome logging before creating the driver:

```python
{"browser": "ALL", "performance": "ALL"}
```

Before each page navigation, call `clear_browser_logs`. After the page has
rendered, call `collect_browser_diagnostics`. This prevents an error from a
previous page from being reported against the next page.

When a diagnostic fails, preserve the URL and include both categories in the
assertion. A readable failure should answer:

- Which page failed?
- Was the problem in JavaScript or the network?
- What URL or request was involved?

For local debugging, remove `--headless` from the local Chrome options fixture
or run pytest with verbose logging. Do not disable diagnostic collection just
to make a test pass.

## 10. Choose the tests that match your solution

The reference test modules are intentionally small:

| Module | Keep it when... | Usually customize... |
|---|---|---|
| `test_install_dependencies.py` | The solution is installed with a real CLI | Prepared-workspace marker and locked dependency status |
| `test_build_installer.py` | The solution produces a desktop artifact | Installer path |
| `test_execute_installer.py` | The artifact has to deploy files | Deployment marker |
| `test_execute_shortcut.py` | Users launch through a desktop shortcut | Shortcut name, platform launch, splash signal, expected PNG asset |
| `test_solution_ui.py` | The solution has a browser UI | Project setup and layout selectors |

Keep setup in `conftest.py` and assertions in test modules. A helper belongs in
`conftest.py` when multiple tests need the same behavior; a one-off business
assertion belongs in the test file for that feature.

## 11. Run the tests in a useful order

Run these commands from the solution root (the `examples` directory for the
reference solution).

Run collection first. It catches import and fixture-name problems without
building or launching anything:

```text
saf execute "pytest --collect-only -q tests/e2e"
```

Then run the inexpensive lifecycle tests before the browser test:

```text
saf execute "pytest -q tests/e2e/test_install_dependencies.py"
saf execute "pytest -q tests/e2e/test_build_installer.py"
saf execute "pytest -q tests/e2e/test_execute_installer.py"
saf execute "pytest -q tests/e2e/test_execute_shortcut.py"
```

Run the browser smoke test after the lifecycle is working:

```text
saf execute "pytest -q tests/e2e/test_solution_ui.py"
```

Run the whole suite with diagnostics visible:

```text
saf execute "pytest tests/e2e -vv -s --setup-show --durations=0 --log-cli-level=INFO"
```

Useful options:

- `-vv` prints detailed test names.
- `-s` shows direct test output.
- `--setup-show` displays fixture setup and teardown.
- `--durations=0` reports every test duration.
- `--log-cli-level=INFO` shows lifecycle progress.
- `--log-cli-level=DEBUG` also shows captured command output.

If the repository has an incompatible globally installed pytest plugin, disable
only that plugin using the option documented by the repository. For example,
the reference environment uses `-p no:pep8` because its installed
`pytest-pep8` plugin is incompatible with pytest 9.

Avoid `pytest-xdist` for the desktop lifecycle unless the fixtures and ports
are explicitly designed for parallel execution. Desktop shortcuts, isolated
environment variables, and application ports can still collide between
workers.

## 12. Troubleshooting

| Symptom | Likely cause | First thing to check |
|---|---|---|
| `fixture ... not found` for Chrome options | The copied suite still expects a fixture from another plugin | Use the local `examples_chrome_options` fixture or rename it for your solution |
| SAF CLI executable not found | `ansys-saf-cli` is not installed in the pytest environment | Install a compatible released CLI and verify `saf --version` |
| Install or build command fails | Wrong CLI, working directory, or solution dependency | Run the logged command manually in the temporary workspace and read captured output |
| Installer not found | Artifact name or output directory differs | Update `_get_installer_path` |
| Shortcut not found | Display name or desktop location differs | Update `SOLUTION_DISPLAY_NAME` and `_get_shortcut_path` |
| API/UI URL timeout | Log message or log directory differs | Update URL regexes and the platform log root |
| Project creation timeout | API endpoint or response shape differs | Adapt `_create_project` |
| No navigation pages discovered | Wrong navigation selector, page not rendered, or all links look like groups | Inspect the DOM and update the navigation constants/helpers |
| A page click times out | Navigation is still updating or the page uses a callback instead of a route | Keep the click inside an explicit retry wait and verify the content/active-link signal |
| Browser reports an old error | Logs were not cleared before navigation | Call `clear_browser_logs` immediately before each page click |
| Test run leaves processes behind | Launcher teardown does not include child processes | Check `LaunchedSolutionProcess.stop` and its `finally` path |
| Linux shortcut cannot launch | `gtk-launch` or `xvfb-run` is missing | Install the tools or replace the Linux launcher for the solution |

When diagnosing a failure, first run one focused test with:

```text
saf execute "pytest <test-path> -vv -s --setup-show --log-cli-level=DEBUG"
```

The fixture logs show the exact lifecycle stage where the failure occurred.

## 13. Final adaptation checklist

Before considering the copied suite ready:

- [ ] A compatible SAF CLI is installed in the environment that runs pytest,
     and `saf --version` succeeds.
- [ ] The solution's test dependencies include Selenium, `psutil`, and
     `httpx2` directly when they are used.
- [ ] No test imports or depends on `ansys-saf-testing`.
- [ ] The solution root and temporary-workspace ignore list are correct.
- [ ] The install command and prepared-workspace assertions are correct.
- [ ] The build artifact path and platform permissions are correct.
- [ ] The installer arguments and deployment marker are correct.
- [ ] The shortcut name, suffix, and location are correct on each supported OS.
- [ ] The launcher stops the complete process tree during teardown.
- [ ] The splash signal and selected PNG asset are valid for each platform where
      they are asserted.
- [ ] The API and UI log patterns match the solution.
- [ ] Project creation or UI-entry setup matches the solution contract.
- [ ] `#navbar-content` and `#page-content` are correct, or the selectors and
      navigation helpers have been adapted.
- [ ] Page discovery finds leaf pages without a hardcoded route list.
- [ ] The browser driver collects console and performance logs.
- [ ] Each page clears old logs, waits for rendering, and checks diagnostics.
- [ ] Feature-specific workflows have dedicated tests in addition to the page
      smoke test.
- [ ] Collection, focused lifecycle tests, browser tests, and the full suite
      have all been run.
- [ ] No solution, browser, driver, or launcher processes remain after pytest.

The result should be a suite that is solution-specific where it must be
specific, but remains reusable across different page sets, navigation labels,
routes, and grouped navigation structures.

---

## Appendix A: function reference

This appendix lists the callable pieces in the reference suite. Use it as a
map before changing or duplicating a helper. The line numbers can change as the
files evolve; the links open the file containing each function.

### Lifecycle and platform helpers

| Function | File | Brief purpose |
|---|---|---|
| `_run_successfully` | [`conftest.py`](./conftest.py) | Runs a command, captures output, and fails clearly on timeout or nonzero exit code. |
| `_wait_for_value` | [`conftest.py`](./conftest.py) | Polls a getter until it returns a value or the timeout expires. |
| `_get_shortcut_path` | [`conftest.py`](./conftest.py) | Builds the expected Windows or Linux shortcut path. |
| `_get_installer_path` | [`conftest.py`](./conftest.py) | Builds the expected platform-specific installer path. |
| `_get_pywin32_pythonpath_entries` | [`conftest.py`](./conftest.py) | Reads pywin32's path-only `.pth` entries without executing code. |
| `_append_test_environment_site_packages_to_pythonpath` | [`conftest.py`](./conftest.py) | Adds the pytest environment's packages and pywin32 paths to installer and launcher subprocesses for the CI-only PIM bridge. |
| `_require_linux_shortcut_tools` | [`conftest.py`](./conftest.py) | Checks that Linux has `gtk-launch` and `xvfb-run`. |
| `_find_splash_image` | [`conftest.py`](./conftest.py) | Waits for the image path selected by the orchestrator and measures when it appears. |
| `_wait_for_http_ok` | [`conftest.py`](./conftest.py) | Waits for a service URL to return HTTP 200. |
| `_check_service` | [`conftest.py`](./conftest.py) | Inner health-check callback used by `_wait_for_http_ok`. |
| `_create_project` | [`conftest.py`](./conftest.py) | Creates a temporary project through the solution API. |
| `_try_create_project` | [`conftest.py`](./conftest.py) | Inner callback that performs one project-creation attempt. |
| `_find_solution_log_url` | [`conftest.py`](./conftest.py) | Finds an API or UI URL in process output or application logs. |
| `_find_url` | [`conftest.py`](./conftest.py) | Inner callback that searches log lines for a matching URL. |

### Browser and page helpers

| Function | File | Brief purpose |
|---|---|---|
| `clear_browser_logs` | [`conftest.py`](./conftest.py) | Clears pending Chrome console and performance logs. |
| `collect_browser_diagnostics` | [`conftest.py`](./conftest.py) | Collects JavaScript errors, HTTP errors, and failed network events while ignoring only `net::ERR_ABORTED` navigation cancellations. |
| `wait_for_page_rendered` | [`conftest.py`](./conftest.py) | Waits until the page-content container exists and contains rendered content. |
| `_get_visible_navigation_links` | [`conftest.py`](./conftest.py) | Returns visible navigation links. |
| `_get_navigation_item_index` | [`conftest.py`](./conftest.py) | Reads a stable item index from a navigation link. |
| `_get_navigation_item_identity` | [`conftest.py`](./conftest.py) | Creates a stable identity from an index, `href`, or label. |
| `_is_navigation_group` | [`conftest.py`](./conftest.py) | Detects whether a navigation link is an expandable group. |
| `_is_navigation_group_expanded` | [`conftest.py`](./conftest.py) | Checks whether a navigation group is open. |
| `_is_navigation_link_active` | [`conftest.py`](./conftest.py) | Checks whether a link represents the current page. |
| `_get_navigation_link` | [`conftest.py`](./conftest.py) | Finds a discovered page in the current live navigation tree. |
| `_click_navigation_link` | [`conftest.py`](./conftest.py) | Waits for a page link to become clickable and clicks it. |
| `click_when_ready` | [`conftest.py`](./conftest.py) | Inner retry callback used while the navigation tree is updating. |
| `_get_navigation_group` | [`conftest.py`](./conftest.py) | Finds a navigation group by stable identity. |
| `_expand_all_navigation_groups` | [`conftest.py`](./conftest.py) | Opens all collapsed navigation groups. |
| `discover_navigation_pages` | [`conftest.py`](./conftest.py) | Discovers every visible leaf page without a hardcoded page list. |
| `_wait_for_page_navigation` | [`conftest.py`](./conftest.py) | Waits for a click to change the route, content, or active link. |
| `page_content_changed` | [`conftest.py`](./conftest.py) | Inner callback that detects changed page-content HTML. |
| `navigation_link_is_active` | [`conftest.py`](./conftest.py) | Inner callback that detects an active navigation link. |
| `navigate_to_discovered_page` | [`conftest.py`](./conftest.py) | Opens one discovered page through the real navigation UI. |

### Launched solution process methods

These methods belong to `LaunchedSolutionProcess` in
[`conftest.py`](./conftest.py).

| Method or property | Brief purpose |
|---|---|
| `__init__` | Prepares the platform-specific shortcut command and log directory. |
| `run` | Creates and starts a process for the installed solution. |
| `process` | Returns the underlying `subprocess.Popen` object. |
| `start` | Starts the launcher and begins capturing its output. |
| `_read_process_output` | Reads launcher output line by line in a background thread. |
| `stop` | Stops the launcher and its child processes. |
| `_terminate` | Terminates one process safely. |
| `log_lines` | Combines launcher output with application log-file contents. |

### Pytest fixtures

All of these fixtures are defined in
[`conftest.py`](./conftest.py). A fixture runs when a test or another fixture
requests it; ordinary helper functions do not run automatically.

| Fixture or inner function | Brief purpose |
|---|---|
| `check_gtk_launch_and_xvfb_are_installed` | Fails early when Linux shortcut tools are missing. |
| `examples_test_environment` | Creates isolated temporary user, desktop, and application-data directories. |
| `_restore_environment` | Restores the user's original environment variables during teardown. |
| `saf_executable` | Finds the SAF CLI from `SAF_EXECUTABLE` or `PATH`. |
| `examples_workspace` | Copies the solution into a clean temporary workspace. |
| `installed_examples` | Runs `saf install -f -d desktop,ui,build` and records the requested groups. |
| `built_examples` | Runs `saf build` and locates the installer. |
| `installed_desktop_examples` | Executes the installer into a temporary installation directory. |
| `launched_examples` | Launches the desktop shortcut and records the selected splash image path. |
| `running_examples` | Waits for services, creates a project, and returns usable URLs. |
| `examples_chrome_options` | Creates self-contained native Selenium Chrome options. |
| `examples_webdriver` | Creates and later closes the session-scoped Chrome driver. |

### Test functions

| Test function | File | Brief purpose |
|---|---|---|
| `test_saf_install_completes_successfully` | [`test_install_dependencies.py`](./test_install_dependencies.py) | Verifies installation succeeds and prepares the workspace. |
| `test_saf_install_verifies_locked_dependencies` | [`test_install_dependencies.py`](./test_install_dependencies.py) | Verifies the selected lock-file dependencies are installed in the solution environment. |
| `test_saf_build_creates_desktop_installer` | [`test_build_installer.py`](./test_build_installer.py) | Verifies build creates a non-empty installer. |
| `test_generated_installer_executes_without_errors` | [`test_execute_installer.py`](./test_execute_installer.py) | Verifies the installer deploys application files. |
| `test_desktop_shortcut_is_created` | [`test_execute_shortcut.py`](./test_execute_shortcut.py) | Verifies the expected shortcut exists. |
| `test_shortcut_launches_solution_and_validates_splash_image` | [`test_execute_shortcut.py`](./test_execute_shortcut.py) | Verifies shortcut launch and the expected PNG asset. |
| `_assert_no_browser_failures` | [`test_solution_ui.py`](./test_solution_ui.py) | Converts browser diagnostics into a readable assertion. |
| `test_solution_ui_is_accessible_in_browser` | [`test_solution_ui.py`](./test_solution_ui.py) | Verifies the initial project page renders without browser failures. |
| `test_discovered_pages_render_without_browser_failures` | [`test_solution_ui.py`](./test_solution_ui.py) | Visits every discovered page and checks rendering and diagnostics. |
