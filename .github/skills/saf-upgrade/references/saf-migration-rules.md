## SAF Migration Procedural Rules

Execute these rules only when the SAF upgrade skill is loaded.

The skill entry point `SKILL.md` is authoritative for the mission, preservation principles, modification scope,
approval gates, high-level workflow, and failure posture. This file contains detailed procedural rules
only. It may elaborate how to execute approved work, but it must not create a second policy or override
the skill entry point. If wording conflicts, stop and report the conflict.

## Scope Contract

Every project path mentioned in these procedures is subject to the Project Access Scopes in the agent
skill entry point:

- the Initial Read Scope is available during the first scan;
- any other project path must first enter the Expanded Read Scope through a purpose-bound approval;
- a path may be modified only after it enters the Approved Write Scope through the applicable gate.

Examples and checklists below identify potentially useful paths; they never authorize access. If a
procedure needs an unapproved path, request the exact file or directory pattern and purpose before
accessing it. If permission is withheld, mark the dependent operation `NOT INSPECTED` and do not describe
it as verified. All inventories, comparisons, snapshots, manifests, validation, and restoration are
limited to their applicable approved scopes.

## Detailed Phase Index

Follow the approved nine-stage runtime workflow from the skill entry point. The 18 detailed phases below
are grouped under those runtime stages and provide the applicable procedural rules; they are not a
second execution sequence or approval path.

1. [**Inspect the project**](#phase-1-inspect-the-project) — Examine the approved project scope
2. [**Determine the current SAF version**](#phase-2-determine-current-saf-version) — Identify the original version
3. [**Determine the latest SAF version**](#phase-3-determine-latest-saf-version) — Find the target version
4. [**Recover the old SAF template**](#phase-4-recover-the-old-saf-template) — Obtain the original reference when available
5. [**Generate the new SAF template**](#phase-5-generate-the-new-saf-template) — Create the target reference
6. [**Build the migration inventory**](#phase-6-build-the-migration-inventory) — Inventory and classify differences
7. [**Apply the template change decision rule**](#phase-7-template-change-decision-rule) — Classify required, optional, and uncertain changes
8. [**Classify file types**](#phase-8-classify-file-types) — Select the correct migration strategy
9. [**Apply deterministic migrations first**](#phase-9-deterministic-migrations-first) — Make approved mechanically safe changes
10. [**Migrate dependencies**](#phase-10-dependency-migration) — Resolve and apply approved dependency changes
11. [**Migrate configuration**](#phase-11-configuration-migration) — Merge structured configuration safely
12. [**Compare and merge source code**](#phase-12-source-code-comparison-and-semantic-merge) — Perform approved semantic merges
13. [**Build the migration plan**](#phase-13-build-the-migration-plan) — Document every proposed change and decision
14. [**Apply the plan**](#phase-14-apply-the-plan) — Apply only explicitly approved changes
15. [**Validate**](#phase-15-validate) — Run the approved tests and checks
16. [**Diagnose failures**](#phase-16-diagnose-failures) — Repair migration-caused failures safely
17. [**Perform the final regression check**](#phase-17-final-regression-check) — Review the final approved state
18. [**Report the final result**](#phase-18-final-result-report) — Summarize outcomes and unresolved work

---

## Phase 1: Inspect the Project

Start by identifying the project root from the path supplied by the user. Do not enumerate the project
root. During the initial scan, inspect only the Initial Read Scope defined in `SKILL.md`.

Within those paths only, search for references to:
- `saf`
- `ansys`
- `solution`
- `ansys-saf-cli`

Do not inspect or claim knowledge of any path outside the approved read scope.
List potentially relevant areas as `NOT INSPECTED`.

> **Do not modify files during this phase** — inspection only.


## Phase 2: Determine Current SAF Version

The command-line executable is `saf`; the package that provides it is `ansys-saf-cli`.
There is no `saf-cli` executable. Run `saf --version` to capture the installed CLI version.
**Identify which SAF version created this project.** Do not assume the installed
`ansys-saf-cli` version reported by `saf --version` is the project version.

**Use these sources in order, but only when each path is in the approved read scope:**
1. `pyproject.toml` — Look for `saf` or `ansys-*` dependencies
2. Dependency files — `requirements.txt`, `setup.py`, etc.
3. Lock files — `poetry.lock`, `uv.lock`, exact pinned versions
4. SAF configuration — Config files with version metadata
5. Generated files — Metadata in generated code
6. Project metadata — Package metadata or scaffold configuration
7. Project files — Comments or documentation

Start with `pyproject.toml`. After Gate A, request an Expanded Read Scope for the exact additional
sources needed to resolve uncertainty. Do not probe likely filenames or list the project root to discover
them. Record every unavailable source as `NOT INSPECTED`.

**Record separately:**
| Variable | Example |
|----------|---------|
| `PROJECT_SAF_VERSION` | `3.2` |
| `INSTALLED_SAF_CLI_VERSION` (from `saf --version`) | `4.0` |

> If version cannot be determined with confidence: **STOP** — do not proceed to destructive changes.

---

## Phase 3: Determine Latest SAF Version

**Find the latest available `ansys-saf-cli` package version.**

- Do **not** hardcode a version number or infer the target from the installed version.
- Query the configured package index without changing it:

  ```bash
  python -m pip index versions ansys-saf-cli
  ```

- Select the highest stable version using semantic version comparison and cross-check it with official
  Ansys release information when available. Use a prerelease only with explicit approval.
- If the index returns no usable versions, stop and report the error. Do not use an invalid install as a
  discovery probe.
- After Gate A, create a temporary environment outside the project. Use its `TEMP_SAF_PYTHON` and
  `TEMP_SAF_EXECUTABLE` for the target CLI and its resolved compatible templates, and remove the environment
  at the end.
- After approval gate A, install the selected exact CLI version:

  ```bash
  TEMP_SAF_PYTHON -m pip install --force-reinstall "ansys-saf-cli==<latest version found>"
  ```

- Verify that the package metadata and executable report the selected CLI version:

  ```bash
  TEMP_SAF_PYTHON -c "from importlib.metadata import version; print(version('ansys-saf-cli'))"
  TEMP_SAF_EXECUTABLE --version
  ```

- If either check disagrees with the selected version, stop and report the mismatch before generating
  templates or modifying the solution. The compatible `ansys-saf-templates` package resolved by the CLI
  is diagnostic context, not a separate target or approval item.

**Record:**
```
CURRENT_PROJECT_VERSION  = 3.2
LATEST_SAF_VERSION       = 4.0
```

> If latest version cannot be determined: **STOP** and report the problem.

---

## Phase 4: Recover the Old SAF Template

The original SAF template is the preferred reference for distinguishing SAF-owned content from user
customizations.

**Possible sources (in order of preference):**
1. SAF CLI — Can it regenerate an older template?
2. Package cache — Local pip/package manager cache
3. Local template archive — An earlier exported clean template
4. Original scaffold command — Official/external documentation, or an exact user-project documentation
   path only after explicit permission
5. Another clean solution — If one exists using the same SAF version

Accept an old template only when its SAF version and relevant template/options match the project. Do not
treat the user's current solution or a nearby template version as `OLD_TEMPLATE`.

After checking the available sources, select and record one comparison mode:

| Comparison mode | Condition | Ownership rule |
|-----------------|-----------|----------------|
| **THREE_WAY** | An exact `OLD_TEMPLATE` was recovered | Use OLD → USER and OLD → NEW to distinguish user and SAF changes |
| **TWO_WAY** | No exact `OLD_TEMPLATE` is available | Compare USER ↔ NEW; never infer ownership from a difference |

Failure to recover an exact old template does not by itself stop the upgrade. In
`TWO_WAY` mode, preserve existing user content by default, disable automatic deletions and
whole-file replacements, and propose only compatibility changes supported by the target SAF APIs or
validation evidence and optional new-template features. Report which recovery sources were checked and
why no exact baseline was available.

---

## Phase 5: Generate the New SAF Template

**Generate a completely clean SAF solution using the latest SAF CLI and its resolved compatible templates.**

```bash
TEMP_SAF_EXECUTABLE --help
TEMP_SAF_EXECUTABLE new --help
TEMP_SAF_EXECUTABLE templates
```

- `TEMP_SAF_EXECUTABLE new` is the supported template-generation command in the current CLI. Read its help output
  and use its exact syntax and options; do not invent flags or subcommands.
- Use `TEMP_SAF_EXECUTABLE templates` to inspect the templates available to the installed CLI and select the
  appropriate template/options for the target version.
- Re-run `TEMP_SAF_EXECUTABLE --help` after installing the target version because command availability
  can vary by CLI version. `TEMP_SAF_EXECUTABLE --version` remains the required command for checking
  the installed version.
- Use the same relevant template/options as the existing solution
- This is a reference project only — do not modify it
- Keep it available for comparison throughout the migration
- After Gate A, run NEW_TEMPLATE once with `--debug` in the temporary environment and record its
  server and browser diagnostics as TEMPLATE_BASELINE. If the original project can run, record
  ORIGINAL_BASELINE the same way before any write.

### Temporary Comparison Copy

After Gate A and before the first write, create a local snapshot and filesystem manifest outside the
project for every path in the Approved Write Scope, including the pre-write state of files that may be
created. A temporary comparison copy may contain only paths in the approved read scope. Do not
recursively copy or enumerate the entire original project. Generated templates and package environments
may be outside the project, but must not be used to inspect unapproved user-project files.

> **Approval gate A:** After the initial scoped read-only scan, present known findings and the initial migration plan in
> readable sections, then — in that same response, without stopping or waiting for a further user message
> in between — use `ask_user` for only this question: `Approve this migration plan?`
> Choices: **Approve**, **Reject**, **Other**. Do not include implementation steps or feature decisions in
> that question. Wait for the answer before installing/upgrading tools or modifying the user project.
> Before this gate, read-only project inspection is limited to the Initial Read Scope. Scoped snapshots,
> expanded project inspection, and reference-template generation occur only after this gate and any
> separately required scope approval.
> Do not require generated-template differences or a complete inventory before Gate A. Mark the
> comparison mode, target details, and proposed changes as pending wherever they cannot yet be
> established. Enrich the plan after approved discovery; the detail-phase numbering does not move
> template generation ahead of Gate A.

---

## Phase 6: Build the Migration Inventory

Create an inventory of every relevant file within the approved read scope in the sources available for
the selected comparison mode:
`OLD_TEMPLATE`, `USER_SOLUTION`, and `NEW_TEMPLATE` for `THREE_WAY`, or `USER_SOLUTION` and
`NEW_TEMPLATE` for `TWO_WAY`.

For every file, classify it using this decision table, and create at least one tracked inventory item
for every difference. A file-level classification is not sufficient when a file contains multiple
independent changes.

| Category | Condition | Action |
|----------|-----------|--------|
| **UNCHANGED** | OLD == USER and OLD == NEW | KEEP as-is |
| **USER_ONLY** | OLD != USER and OLD == NEW | KEEP USER VERSION |
| **SAF_ONLY** | OLD == USER and OLD != NEW | TAKE NEW SAF VERSION |
| **CONFLICT** | OLD != USER and OLD != NEW and USER != NEW | SEMANTIC MERGE |
| **NEW_SAF_FILE** | OLD doesn't exist, USER doesn't exist, NEW exists | ADD new file |
| **USER_FILE** | OLD doesn't exist, USER exists, NEW doesn't exist | KEEP user file |
| **SAF_DELETED** | File exists in OLD and USER, not in NEW | Consider removing |
| **USER_DELETED** | File exists in OLD and NEW, not in USER | Note user deletion |
| **UNKNOWN** | Unclear classification | PRESERVE + REPORT |

When the comparison mode is `TWO_WAY`, use this classification table instead:

| Category | Condition | Action |
|----------|-----------|--------|
| **COMMON** | USER == NEW | KEEP as-is |
| **USER_OR_LEGACY_FILE** | USER exists, NEW does not | PRESERVE + REPORT |
| **NEW_TEMPLATE_CANDIDATE** | USER does not exist, NEW exists | PROPOSE as an individual opt-in or required compatibility change |
| **UNKNOWN_BASELINE** | USER and NEW both exist and differ | PRESERVE USER; propose only evidence-backed, minimal changes |

`TWO_WAY` cannot produce `USER_ONLY`, `SAF_ONLY`, `CONFLICT`, `SAF_DELETED`, or
`USER_DELETED`, because those classifications require a known old baseline. Do not remove a user file,
restore an apparent deletion, or replace an existing file based only on the two-way comparison.

The inventory is exhaustive within the approved read scope: compare file existence, paths, contents,
configuration keys, dependency versions, imports, signatures, routes, pages, controls, callbacks,
assets, tests, and runtime behavior that are present in that scope. Record both additions and removals
within the scoped comparison, including scoped user content absent from the new template and scoped
template content absent from the user project. Record each difference with its exact files, symbol or
configuration key, available OLD value, USER value, NEW value, classification, behavior impact,
evidence, and required decision. Mark OLD as `NOT AVAILABLE` in two-way mode. Mark relevant user-project
areas outside the approved read scope as `NOT INSPECTED`; do not infer their contents. Do not collapse
multiple differences into one row or omit differences because they appear cosmetic, redundant, required,
or difficult to merge.

Before any approval prompt, reconcile the inventory against the selected comparison and report:


INVENTORY RECONCILIATION
Runtime stage: <current stage>
Comparison mode: <THREE_WAY | TWO_WAY>
Baseline status: <exact source and version | NOT AVAILABLE>
Compared differences found: <count>
Differences listed: <count>
Differences missing from the plan: 0
Decision items in this stage: <count>
Approval interaction: <Gate B table | individual source-change prompts>


Do not claim that pending differences already have answers. If the listed-difference count does not
equal the compared-difference count for this stage, or its missing-plan count is non-zero, repair this
stage's inventory before asking for its change decisions. Update the decision record after each answer
and apply only that answer's approved scope. At the end of the stage, report:


DECISION RECONCILIATION
Runtime stage: <current stage>
Decision prompts issued: <count>
Explicit answers recorded: <count>
Decided inventory items: <count>
Pending items in this stage: <count>
Pending later-stage items: <count>


Each issued prompt must have an explicit answer before its action. Gate B's one table answer may
cover multiple dependency inventory items. Source changes require one answer per item, obtained
immediately before applying that item; other source items may still be pending. Require zero pending
items in the current stage before leaving it, not before applying its first approved item. Later-stage
items remain pending until their stages. Reconcile the full inventory only at final verification.

---

## Phase 7: Template Change Decision Rule

For every meaningful template difference that affects source code, configuration, or runtime behavior,
classify it before editing. In `THREE_WAY` mode, derive template changes from `OLD_TEMPLATE` →
`NEW_TEMPLATE`. In `TWO_WAY` mode, treat `NEW_TEMPLATE` content absent from or different
to `USER_SOLUTION` as a candidate rather than proof of a SAF-owned change:

1. **Required compatibility change** — needed for the approved dependency upgrade or for the project
   to build, start, or validate with the upgraded SAF version.
2. **Optional template functionality or behavior change** — useful or recommended by the new template,
   but not needed for compatibility.
3. **Unrelated or uncertain change** — not clearly required or not safely attributable to SAF.

In two-way mode, classify a change as required only when target-version package APIs, official targeted
documentation, or validation evidence independently demonstrates the compatibility need. A difference
from `NEW_TEMPLATE` alone is insufficient. Classify all other new-template differences as optional or
uncertain, preserve the user version by default, and do not propose deletion of existing user content.

List every item in the migration plan with its classification, affected files,
exact difference, and behavior impact. Every item requires its own clickable **Approve / Reject / Other**
decision prompt before that item's implementation in its assigned stage, including required compatibility changes, preservation choices,
deletions, additions, cosmetic changes, and uncertain changes. Optional changes require a separate
prompt; do not silently apply, preserve, or omit any difference. Unrelated or uncertain changes must be
preserved by default only after they have been reported and explicitly rejected or otherwise decided by
the user.

For each prompt, define the action explicitly: **Approve** applies only that proposed `NEW_TEMPLATE`
change; **Reject** preserves the `USER_SOLUTION` value or file; **Other** pauses that item for a
separate typed instruction. For `SAF_DELETED`, **Approve** means remove only after confirming the file
is SAF-owned; for `USER_DELETED`, **Reject** preserves the user's deletion; for `UNKNOWN`, **Approve**
is not allowed until ownership and the proposed action are clarified. Never use one decision for
multiple source differences. Dependency decisions instead follow Gate B's explicitly displayed table:
one Gate B answer covers exactly its listed rows and lock-file/source actions. No backend/UI decision
is required before implementing those approved dependency actions.

---

## Phase 8: Classify File Types

Before migrating, classify each file in the approved read scope into one category. The examples below
select a strategy; they do not authorize reading or modifying those paths.

| Category | Examples | Strategy |
|----------|----------|----------|
| **SOURCE** | `.py`, `.js`, `.ts`, `.cpp` | Semantic merge using the selected comparison mode |
| **DEPENDENCY** | `pyproject.toml`, `requirements.txt`, `setup.py` | Careful version merging |
| **CONFIGURATION** | `.yaml`, `.json`, `.toml` (config files) | Structured merge |
| **TEST** | `test_*.py`, `*_test.py` | Preserve user tests, update imports |
| **CI** | `.github/workflows/*.yml`, `.gitlab-ci.yml` | Merge incrementally |
| **DOCUMENTATION** | `*.md`, `docs/` | Preserve user docs |
| **GENERATED** | Marked as auto-generated | Replace only when ownership and unchanged status are confirmed; otherwise preserve |
| **STATIC** | Assets, images, data files | Preserve user assets |
| **UNKNOWN** | Unclear | PRESERVE + REPORT |

---

## Phase 9: Deterministic Migrations First

After the relevant inventory item has been individually approved, perform changes that are
**mechanically safe** before reasoning about source code:

**Examples of safe changes:**
- Adding new SAF-owned files (that don't exist in user solution), only after that file/difference is approved
- Replacing unchanged SAF files with new versions, only after that replacement is approved
- Updating known SAF dependency versions (with compatibility checks and explicit approval of each
  listed row through the Gate B table)
- Renaming known SAF files (if the individual mapping is documented and approved)
- Updating structured configuration (TOML, JSON, YAML), with each changed key approved individually
- Regenerating lock files, only after the exact lock-file changes are approved

**For structured files, use parsers:**
- Use TOML parser for `pyproject.toml` — not text replacement
- Use JSON/YAML parsers for config files — not regex
- Use Python AST for source code analysis — not line-by-line grep

Do not use "deterministic", "generated", "unchanged", or "required" as a reason to bypass the
applicable approval. Source items require individual prompts; dependency rows and their listed
source/lock actions use Gate B.

Use deterministic replacement or rename only for files confirmed to be SAF-owned and unchanged by the
user. This restriction does not prevent an individually approved minimal compatibility edit under the
source and configuration rules. Preserve generated files if they contain user changes or their ownership
is uncertain.

---

## Phase 10: Dependency Migration

**Never replace the user's dependency file with the latest template.**

Only upgrade SAF dependencies, such as `ansys-saf-glow-engine`, `ansys-solutions-dash-super-components`, and related `ansys-saf-*` packages. Change non-SAF dependencies only when a new SAF version requires it and the user explicitly approves it.

Use the selected comparison mode for dependency ownership:

```
OLD_TEMPLATE deps  +  USER_SOLUTION deps  +  NEW_TEMPLATE deps
         ↓                  ↓                        ↓
  OLD SAF deps      USER ADDED deps         NEW SAF deps
```

When `OLD_TEMPLATE` is unavailable, compare the current direct SAF/Ansys declarations with the target
requirements and preserve every unrelated or user-added declaration. Do not infer that a dependency is
obsolete merely because it is absent from `NEW_TEMPLATE`, and do not remove it without independent
compatibility evidence and explicit approval.

**For each dependency, determine:**
- Is it SAF-owned based on package identity or the exact old baseline?
- Is it user-owned, or must it be preserved because ownership cannot be established?
- Is there a conflict?

For each dependency prioritise the public versions on PyPI. Check all possible dependencies' public versions for the upgrade first. If a public version is not available, report it.

Do not tighten dependency version possibilities during an upgrade. Preserve the existing constraint
shape and its open-ended behavior whenever possible: never turn a range into an exact pin, never add
an upper bound that was not already present, and raise only the lower bound required for compatibility.

### Dependency Backend

Detect the project's existing dependency backend before resolving:

- Poetry: `[tool.poetry]` with `poetry.lock`; use `poetry lock`.
- uv: `uv.lock` or `[tool.uv]`; use `uv lock`, then `uv sync --locked` only when the approved lock must be
  installed into the environment without allowing uv to rewrite it.
- Requirements-only projects: use the existing documented resolver and lock process.

If multiple backends or lock files are present, stop and ask which one is authoritative. Do not convert
between Poetry, uv, and another backend during a SAF upgrade. Run the selected lock command only after
dependency approval; never use `uv sync --locked` as a substitute for `uv lock`. Review the complete lock-file
diff; transitive non-SAF changes require explicit approval.

Each canonical dependency may
appear only once in the final dependency files. Collapse duplicates into one declaration while
preserving the broadest compatible constraint and required source/prerelease settings. If a dependency
is declared in more than one group, keep one declaration in the main dependency table when that is
necessary to preserve availability across the groups, remove the group copies, and report the broader
installation scope as a risk. If duplicates have incompatible constraints or group scopes, report the
conflict and propose the smallest consolidation that satisfies all known consumers; do not silently
discard a group or constraint.


> **Approval gate B — required interaction order:** First render the complete dependency decision
> table to the user in the assistant message. Include every direct SAF dependency, every required
> non-SAF dependency exception, the proposed version, reason, and breaking-change risk in the table.
> State the affected dependency/lock files immediately below it; do not add them as table columns.
> Do not call `ask_user`, show a “Waiting for answer” state, or ask any
> dependency question before that table has been displayed.
>
> After the table is displayed, call `ask_user` exactly once with the short question
> `Approve these dependency changes?` and clickable choices **Approve**, **Reject**, and **Other**.
> **Approve** authorizes only the rows shown in the table and the explicitly listed lock-file refresh;
> **Reject** leaves all dependency files unchanged; **Other** opens a separate free-text follow-up.
> Never put the dependency table, a long explanation, multiple decisions, or feature decisions inside
> the clickable question. Do not install packages, edit dependency files, or run a lock update until
> the answer is received.
>
> Display the table first within the same assistant response, then immediately invoke `ask_user` in
> that same response, without stopping or waiting for a further user message in between. The approval
> control must never be created before the table or in place of any part of it.

Use this exact presentation order. Render it as normal Markdown, without a fenced code block,
ASCII-table formatting, or terminal formatting:

DEPENDENCY DECISION — Gate B

| Dependency | Current version | Proposed version | Reason | Risk / breaking change |
|---|---|---|---|---|
| ... | ... | ... | ... | ... |

Upgrade order: <short ordered list based on the dependency graph>
Private source URL action: <none, or old private package's source/URL → target URL>
Duplicate dependency action: <none, or exact declarations consolidated and retained>
Affected dependency/lock files: <exact files>
Lock-file action: <none, or exact files and refresh proposed>
Non-SAF exceptions: <none, or exact rows requiring approval>


Then ask interactively: `Approve these dependency changes?`
Choices: **Approve** / **Reject** / **Other**

**Handle conflicts:**
1. If user dependency is incompatible with new SAF version:
   - Identify the conflict
   - Check if a compatible version exists
   - Migrate if safe
   - Otherwise, report and require manual intervention. Among the proposed choices, propose also a solution which is skipping the impossible dependency upgrade and passing to the updates. After the maximum repair attempts are exhausted,
     use the unresolved-conflict escalation described in Phase 16; do not change dependencies as part of
     that escalation.

**Result:** User dependencies + new SAF dependencies (both compatible)

---

## Phase 11: Configuration Migration

For structured configuration files (YAML, JSON, TOML):

1. **Parse** every version available in the selected comparison mode
2. **Compare** keys and values; identify ownership only when the old baseline supports it
3. **Migrate** confirmed SAF-owned changes, or minimal evidence-backed compatibility changes in two-way mode
4. **Preserve** user-owned values
5. **Validate** the resulting configuration

> Do not blindly overwrite configuration files.

In `TWO_WAY` mode, preserve every existing key and value unless a separately approved target
compatibility requirement proves it must change. Treat keys found only in `NEW_TEMPLATE` as individual
new-template candidates, and never remove a user key solely because the new template omits it.

Configuration changes that can alter runtime behavior require a separate approval, even when they are present in the new template.

---

## Phase 12: Source Code Comparison and Semantic Merge

Use a semantic three-way merge when an exact old baseline exists:

**In `THREE_WAY` mode, reason from these three versions:**
- `OLD_TEMPLATE` — The baseline
- `USER_VERSION` — What the user changed
- `NEW_TEMPLATE` — What SAF changed

**Determine:**
- What changed in SAF (OLD → NEW)?
- What changed in user code (OLD → USER)?
- Are these changes **independent** or **conflicting**?

**In `TWO_WAY` mode, reason from:**
- `USER_VERSION` — The behavior and customizations to preserve
- `NEW_TEMPLATE` — A source of target-version compatibility patterns and optional features
- Target SAF package APIs, focused official documentation, and validation results — Independent evidence
  for required compatibility changes

Determine the smallest change required for target compatibility without attributing unmatched code to
SAF or the user. Preserve the user implementation when evidence does not require a change. Never
automatically delete code, replace a whole existing file, or adopt a redesign in this mode. Present each
new-template feature separately for opt-in approval under the existing backend and UI gates.

Apply the preservation and scope principles from `SKILL.md`; the rules below add only
phase-specific backend/UI decisions, merge confidence, and application mechanics.

### Backend Template Features

For backend functionality introduced by `NEW_TEMPLATE` but absent from `USER_SOLUTION`, list every
proposed service, route, model, storage example, import, signature change, and other behavior in the
migration plan. Mark whether each change is required for compatibility with the approved SAF dependency
upgrade. Every listed change requires its own explicit clickable **Approve / Reject / Other** prompt
before it is applied, including required compatibility changes. Never treat a dependency approval,
Gate C approval, general migration-plan approval, or "required" classification as approval for a
specific backend change. Do not infer an opt-out from the fact that a feature is not currently used,
and do not silently omit any proposed change as "template functionality."

| File/component | Proposed backend change | Required for compatibility? | Behavior impact | Opt-in/opt-out decision | Approval |
|----------------|-------------------------|-----------------------------|-----------------|------------------------|----------|

### `src/solution/` Restriction

List every proposed `src/solution/` change in a table before editing. Only modify imports, function/class signatures, and the minimum compatibility adaptations required by approved SAF dependency upgrades. Never change solution logic or business behavior without separate, specific approval. This restriction takes precedence over the general semantic-merge guidance above.

| File | Change | Required for dependency compatibility? | Behavior impact | Opt-in/opt-out decision | Approval |
|------|--------|------------------------------------------|-----------------|------------------------|----------|

For every non-empty row in this table, use this sequence:

BACKEND CHANGE C<n>
File: <one file>
Change: <one specific edit>
Reason: <compatibility or template feature>
Impact: <user-visible or internal behavior>


Then invoke `ask_user` with only the question `Approve this backend change?` and the clickable choices
**Approve**, **Reject**, and **Other**. Split a row if it contains more than one independently
approvable edit. An empty table is the only case where no backend-change prompts are required.

> **Approval gate C:** Before editing `src/solution/`, first display the complete table of proposed
> changes. Then ask one separate clickable prompt per row, in table order, using the short question
> `Approve this backend change?` and choices **Approve**, **Reject**, and **Other**. This applies equally
> to required compatibility work and optional template functionality. Do not ask one aggregate Gate C
> question, and do not begin editing after dependency approval alone. **Approve** authorizes only that
> row; **Reject** preserves the current code; **Other** opens a separate free-text follow-up. Do not
> show the next prompt until the current row has been answered. If any proposed row has no prompt and
> explicit answer, stop and report the omission instead of skipping that change.

> If the backend table is empty, show `BACKEND STATUS — No proposed backend changes` together with the
> checks that produced that result; do not claim that backend differences were reviewed without showing
> the comparison basis. Continue without a backend-change prompt only after the exhaustive inventory
> confirms that there are zero backend differences.

**Example:**
```python
OLD:  def process(data):
      return transform(data)

USER: def process(data):
      log("processing")
      return transform(data)

NEW:  def process(data, config):
      return transform(data, config)

MERGED: def process(data, config=None):
        log("processing")
        return transform(data, config)
```

### Merge Confidence Levels

Assign a confidence level to each merge:

| Level | Condition | Action |
|-------|-----------|--------|
| **HIGH** | Exact baseline exists and SAF and user changes are independent | Apply after the relevant approval gate |
| **MEDIUM** | Changes reconcile safely, or a minimal two-way compatibility edit has independent API or validation evidence | Apply after approval, with verification |
| **LOW** | Same logic changed substantially, ownership is material but unknown, or two-way evidence is insufficient | STOP — report conflict, require manual review |

> For LOW confidence: **DO NOT SILENTLY APPLY** — make the conflict explicit.
> A two-way comparison cannot receive HIGH confidence because it cannot prove ownership or independence
> from an old baseline.

If a conflict remains unresolved after the allowed repair attempts, regardless of whether it was found
in dependencies, backend code, UI code, configuration, or validation, follow the Phase 16 unresolved-
conflict escalation. Do not stop with only a manual-review report: first present the per-feature
backend/UI decision prompts, freeze dependencies, and wait for the user's choices.

### Consulting Official Documentation for Low-Confidence Merges

Before downgrading a merge to LOW confidence solely because the correct target-API pattern is unclear
(e.g. which replacement class/method a removed SAF API maps to), follow the skill's Trusted External
Resources rules to identify a relevant exact official documentation page and consult only that page.
If no relevant page can be identified, ask the user for its URL or report the documentation check as
blocked; do not invent a URL. This may raise the merge to HIGH or MEDIUM confidence in three-way mode, or to
MEDIUM confidence in two-way mode, if it resolves the ambiguity; otherwise keep the LOW classification
and report what remains unclear. This does not relax the inspect-the-actual-packages-first rule in
`SKILL.md`.

For every approved dependency with a major-version change, also read its release notes or migration
guide (identified from package metadata) and list the breaking changes that affect the project's code
before applying source changes. Use NEW_TEMPLATE patterns only as a cross-reference.

---

## `src/ui/` Update Rules

List every proposed UI change before editing:

| File/page | API breaking change | Behavior impact | New feature | Approval |
|-----------|---------------------|-----------------|-------------|----------|

- Fix API-breaking component parameters and callback signatures, and any NEW diagnostic caused by the
  approved dependency upgrade, using the smallest behavior-preserving edit.
- Preserve every existing page, navigation link, callback, and behavior.
- Do not add template features automatically, and do not silently omit them from the migration
  discussion. For every feature or redesign present in the new template but absent from the current
  project, ask a specific opt-in/opt-out question before editing. The question must explicitly cover
  the user-visible impact and list the exact proposed files.
- Ask for approval separately for every behavior-changing UI change and every new feature. A general
  approval to upgrade SAF does not approve adopting the new template's AppShell/theme, adding pages,
  changing navigation, changing callbacks, or adding entity-storage examples.
- Stop and ask if identical behavior cannot be maintained.

> **Approval gate D:** Before each `src/ui/` change, wait for an explicit answer to that individual
> UI/template decision, including whether to adopt the new template's AppShell/theme, new pages,
> navigation/callback changes, and entity-storage examples. An opt-out is an explicit decision to
> preserve the current behavior; it is not permission to skip asking. If the user opts in, include
> that feature in the approved plan and implement it within the modification scope. If the user opts
> out, preserve the current implementation and record that decision. Apply the approved item before
> presenting the next one, in required-then-optional stage order; do not wait for all UI decisions
> before applying the first approved UI change.

---

### Per-feature decision prompts

Do not consolidate these decisions into a required-decision list or a single approval question. Ask one
prompt for every independently observable backend or UI feature/design difference, including
differences such as a title/header color, page registration versus a hardcoded page list, a new page,
navigation, callback behavior, or calculator-result storage.

Use this format in the plan and approval requests. The context is displayed separately from the
clickable question:

```
FEATURE 1 — Redesigned Dash shell and theme controls

Affected files:
  src/ui/app.py
  src/ui/layout.py

Change:
  The new template uses a white title/header instead of the current black one.

Question: Adopt this redesigned shell?
Choices: Approve / Reject / Other
```

For each feature, call `ask_user` with exactly one short question and these clickable choices:
**Approve**, **Reject**, **Other**. If **Other** is selected, ask a separate free-text follow-up. Never
present multiple features in one `ask_user` call or one question. Ask the next feature only after the
previous feature has been answered.

Use exactly one interactive choice per prompt. **Approve** means implement the corresponding new-template
behavior; **Reject** means preserve the current implementation; **Other** means ask a follow-up free-text
question and follow the user's instruction only after clarifying any ambiguity. Required compatibility
fixes are not optional features and must be listed separately from these prompts. Do not proceed when a
choice is missing or ambiguous. If the host does not expose `ask_user`, stop and report that the
interactive approval tool is unavailable rather than substituting a typed checklist.

---

## Phase 13: Build the Migration Plan

Before applying changes, create and review a migration plan.

**Plan format:**

```
SAF UPGRADE PLAN
================

FROM: SAF 3.2
TO:   SAF 4.0
COMPARISON: THREE_WAY / TWO_WAY
BASELINE: <exact version/source> / NOT AVAILABLE

ADD (new files):
  - src/foo/new_feature.py
  - pyproject.toml (new section)

UPDATE (modifications):
  - pyproject.toml (dependency versions)
  - src/foo/app.py (semantic merge)
  - requirements.txt

PRESERVE (no changes):
  - src/foo/custom_solver.py
  - src/foo/tests/custom_solver_test.py
  - docs/custom_feature.md

MERGE:
  - src/foo/app.py (HIGH confidence)
  - src/foo/config.py (MEDIUM confidence)

MANUAL REVIEW REQUIRED:
  - src/foo/legacy.py (LOW confidence - SAF API changed, user customized)
  - .github/workflows/deploy.yml (uncertain if user-modified)

Validation Commands:
  pytest
  make lint
  make build
  saf build
```

> **Do not hide conflicts inside the plan.** Explicitly list uncertain items.

The plan must include:
- Project path and temporary comparison-copy path
- Current and target SAF CLI versions
- Selected comparison mode, old-template baseline status, and attempted recovery sources
- SAF-only dependency changes and dependency order
- `src/solution/` import/signature changes
- `src/ui/` API changes and any proposed new features
- Files preserved, added, modified, merged, or requiring manual review
- Exact validation and end-to-end comparison commands
- The complete inventory reconciliation counts and every listed difference
- A one-to-one mapping from every listed difference to its individual approval prompt and recorded answer

Do not proceed to implementation until every listed difference has an explicit individual decision. A
general plan approval is not sufficient, and a difference with no proposed code edit still requires a
recorded **Reject** or **Other** decision when it represents a template/user difference. If the
inventory, plan, prompts, and recorded answers do not have identical coverage, stop and report the
mismatch.

---

## Phase 14: Apply the Plan

Apply only the changes approved in the migration plan and at the relevant approval gates.

Before applying any change, verify that the corresponding listed difference has exactly one recorded
**Approve** answer.
Never infer approval from a dependency gate, implementation gate, category, compatibility requirement,
previous decision, or silence. Rejected items must remain unchanged; Other items require a clarified
custom instruction before implementation. At completion, reconcile applied, preserved, rejected, and
unresolved differences against the full inventory; any missing difference is a migration failure.

Apply changes in this specific order:

1. Update approved dependencies using the selected comparison strategy.
2. Regenerate only explicitly approved dependency/lock files within the modification scope.
3. Apply approved required changes under `src/solution/`, including new SAF files, safe SAF-only
   changes, parsed configuration updates, and semantic source merges.
4. Apply approved optional changes under `src/solution/`, including optional template functionality
   only when its separate opt-in approval is recorded.
5. Apply approved required changes under `src/ui/`, using the same deterministic, structured, and
   semantic-merge rules.
6. Apply approved optional changes under `src/ui/`, including optional template functionality only
   when its separate opt-in approval is recorded.
7. Validate the result.

**After each significant stage:** record a filesystem manifest for the Approved Write Scope, including
each relative path, size, and SHA-256 hash. Compare it with the previous manifest and the approved plan.
Do not use repository version-control commands or claim that paths outside that scope were checked.

If a new conflict or out-of-scope change appears, stop immediately and ask for approval rather than expanding the plan.

---

## Phase 15: Validate

**Use the project's existing validation commands whenever possible.**

**Discover available commands only from approved sources:**
- `pyproject.toml` — Look for `[tool.poetry.scripts]` or `[project.scripts]`; this is in the Initial
  Read Scope.
- `Makefile` — Inspect only if the exact path is in the Expanded Read Scope.
- `README.md` — Inspect only if the exact path is in the Expanded Read Scope.
- CI configuration — Inspect only if the exact file or directory pattern is in the Expanded Read Scope.
- SAF CLI — `saf --help`; account for any project paths the command may access before running it.

**Run these validations (if available):**
- ✓ Syntax checks
- ✓ Unit tests (`pytest`, `unittest`)
- ✓ Integration tests
- ✓ Lint checks (`flake8`, `pylint`)
- ✓ Type checks (`mypy`, `pyright`)
- ✓ SAF build/package validation (`saf build`)

**Do the End-to-End Verification**

**Do not invent commands.**

First inspect:
```bash
saf --version
saf --help
saf new --help
saf templates
saf install --help
saf build --help
saf run --help
```

Use only commands actually supported by the installed version.

### Scoped End-to-End Verification

Even if no backend or UI files were modified, verify the complete functional inventory derived from the
approved read scope. Compare the upgraded solution with the scoped temporary copy and verify, one by one:

- content of every inventoried page;
- every inventoried navigation link;
- every inventoried callback;
- the layout represented in the inventory;
- existing functionality and user workflows represented in the inventory.

Classify each diagnostic: NEW (absent from the available baselines, so repair it), IN_TEMPLATE (also in
TEMPLATE_BASELINE, so report it), or PRE_EXISTING (in ORIGINAL_BASELINE, so report it). If no baseline
could be recorded, treat every diagnostic as NEW and say so.
Report any unresolvable difference and every relevant path or behavior that was `NOT INSPECTED`. If
verification requires starting a service or browser, obtain approval at gate E first.
The functional inventory is the acceptance checklist. Every page and every inventory item must have an
individual `PASS`, `FAIL`, `NOT AVAILABLE`, `NOT INSPECTED`, or `BLOCKED BY ENVIRONMENT` result. Do not
summarize a page as working based only on its initial load. Do not declare the approved scope successfully
verified while an in-scope item is untested or failing. If a browser or service cannot be used, explicitly
report the exact page, control, callback, and workflow items that remain unverified. Never present this
scoped result as whole-project verification.

### Mandatory Live Debug Verification Protocol

Static imports, compilation, dummy tests, and callback-signature inspection are not sufficient
end-to-end verification. When the solution has a runnable UI, the upgrade is not complete until
the live application has been started and exercised.

Follow this protocol after every upgrade:

1. Inspect `saf run --help` and use the installed CLI's supported run command.
2. Start the solution with debug logging enabled (`--debug` when supported) and retain the
   process output. Do not report success if the process exits, cannot bind its port, or logs
   callback/import/runtime errors.
3. Open the actual running UI in a browser. If the solution requires a project/API/container, create or
   start that prerequisite only when its command and required project paths are in the approved read scope.
   Capture all available diagnostics for the whole session, starting before the first page load: server
   output/logs, browser console (errors and warnings), page exceptions, failed requests. Record each
   distinct message and its count per page. Any source that cannot be captured is reported as UNKNOWN,
   never as clean.
4. Verify every inventoried page individually:
   - expected headings, controls, images, icons, navigation links, and theme/layout elements
     are present;
   - direct URL navigation and navigation-menu navigation both work.
5. Verify every callback and user workflow individually:
   - trigger each callback through its real UI control;
   - confirm the visible output/state change;
   - inspect debug/server output for exceptions;
   - cover success, empty/default, and invalid-input paths where the UI exposes them.
6. For calculation or storage features, use known inputs and assert the exact result. For example,
   a two-number sum must be checked with non-zero and negative values, and save/load must be
   checked across the actual UI controls.
7. Check documentation, portal/back links, theme toggles, uploads, downloads, and other header/
   navigation features whenever present.
8. Capture a verification matrix containing each page, control/callback, input, expected result,
   observed result, browser/server diagnostics, and pass/fail status. A single failed item or NEW
   diagnostic requires diagnosis and repair before completion.
9. Reconcile the matrix against the functional inventory by verification. Missing IDs are
   unverified behavior, not implicit passes.

### Required Regression Tests

When an upgrade changes a callback, page, or user-visible feature, add or update executable tests only
when the exact test paths have separately entered the Approved Write Scope. If test write access is not
approved, report the missing regression coverage instead of creating or modifying tests. When approved,
cover at minimum:

- test each backend transaction and model behavior;
- test each UI callback directly with a fixture/project or through the live browser;
- test page registration and unique route paths;
- test required header controls (documentation and portal links when configured);
- test the primary workflow with representative positive, negative, default, and persistence cases;
- test that the upgraded app imports and starts without duplicate page registration;
- test that every registered page loads without a diagnostic (a smoke test or documented browser script).

Do not treat `test_expected_to_pass` or other placeholder/dummy tests as coverage of upgraded
behavior. If the repository lacks the necessary fixtures, add the smallest project-conforming
fixtures/tests within the approved scope or explicitly report the unverified behavior and stop.

---

## Phase 16: Diagnose Failures

### Local Rollback

Keep the pre-migration snapshot until the final report. If the run fails, is cancelled, or ends with an
unresolved conflict, stop applying changes, restore every snapshotted file, remove files created by the
migration, and remove temporary copies, generated templates, and temporary environments. Compare a new
filesystem manifest for the Approved Write Scope with the pre-migration manifest. Do not report
completion until every path in that scope is restored or the exact restoration failure is reported.
Do not claim that paths outside that scope were compared.

If validation fails, determine the **root cause category:**

| Failure Type | Meaning | Action |
|--------------|---------|--------|
| **MIGRATION_FAILURE** | Bug in the migration itself | Repair it |
| **DEPENDENCY_FAILURE** | Missing or incompatible package | Adjust dependencies |
| **SAF_FAILURE** | Problem with SAF CLI or SDK | Report, may need manual fix |
| **USER_CODE_FAILURE** | Problem in user's code (not caused by migration) | Do not fix — report |
| **ENVIRONMENT_FAILURE** | Missing tool or config | Fix environment or document |
| **PRE_EXISTING_FAILURE** | Existed before migration | Do not fix — report |

**Repair process:**

```
FAILURE
   ↓
Identify changed file causing failure
   ↓
Inspect OLD, USER, NEW versions side-by-side
   ↓
Determine what went wrong in the migration
   ↓
Repair the migration error
   ↓
Validate again
```

Only repair failures caused by the approved migration. Do not modify unrelated user code to make validation pass. If a repair could change behavior or exceed the approved scope, stop and ask for approval.

**Maximum automatic repair attempts: 3**

After 3 unsuccessful attempts:
```
⚠️  MANUAL_INTERVENTION_REQUIRED
```

Stop the migration and explicitly tell the user which conflict remains unresolved. Dependency changes
are now frozen: do not edit dependency constraints, regenerate lock files, install packages, or retry
the dependency resolution. Then ask whether approved backend and UI template features should still be
applied despite the unresolved dependency conflict. This is a separate decision from resolving the
conflict and must not be phrased as a single yes/no question.

Present the decision as a per-feature prompt using the format in the "Per-feature decision prompts"
section. Include every proposed backend and UI feature that can still be applied independently, with
one interactive **Approve** / **Reject** / **Other** choice per item and the exact affected files.
If the user chooses to continue, apply only the individually selected backend/UI features, preserve
the unresolved conflict for manual intervention, and leave all dependency files unchanged. If a
feature depends on the unresolved dependency, mark it **BLOCKED** rather than applying it. Do not
resume an item's implementation until its applicable prompt has an explicit choice. Preserve the
required-then-optional backend/UI stage order, applying each independent approved item before asking
for the next. Do not require answers to all remaining feature prompts before applying the first item.

---

## Phase 17: Final Regression Check

Before declaring success, verify the migration is correct:

**Within the approved read and write scopes, verify these user-owned items still exist:**
- ✓ User-created files
- ✓ User source code (unchanged/properly merged)
- ✓ User tests
- ✓ User dependencies (compatible versions)
- ✓ User configuration

Verify user tests only when their exact paths were separately approved for inspection.

**Within the approved read and write scopes, verify these SAF-owned items are present:**
- ✓ New required SAF files
- ✓ Migrated SAF APIs (deprecated APIs updated)
- ✓ Separately approved optional SAF features available, or opted-out features preserved and documented
- ✓ SAF configuration updated

**Within the Approved Write Scope, verify these deletions are expected:**
- ✓ Obsolete SAF files removed only when confirmed SAF-owned and approved
- ✓ No unexplained file deletions

**Inspect:** compare the final Approved Write Scope manifest with the pre-migration manifest and approved
plan. Only approved additions, modifications, and deletions may remain in that scope. Check file encoding,
whitespace, and patch sanity with local tools; do not use repository version-control commands. Report
all relevant areas outside the approved read scope as `NOT INSPECTED`.

---

## Phase 18: Final Result Report

Provide a structured summary:

```
SAF SOLUTION UPGRADE
====================

Status:       SUCCESS / PARTIAL / FAILED

SAF:          3.2 → 4.0
Comparison:   THREE_WAY / TWO_WAY
Baseline:     <exact version/source> / NOT AVAILABLE
Initial Read: <paths>
Expanded Read:<approved paths or NONE>
Write Scope:  <approved paths or NONE>

Files:
  Added:      5
  Modified:   12
  Preserved:  28
  Deleted:    3
  Merged:     7

Validation:   PASS / FAIL
Tests:        PASS / FAIL / NOT AVAILABLE
Build:        PASS / FAIL / NOT AVAILABLE

Manual Intervention:  NONE / REQUIRED
Local Artifacts:      REMOVED / MANUAL CLEANUP REQUIRED
Restoration:          NOT NEEDED / COMPLETE / FAILED
```

**For every manual intervention, document:**

```
File: src/legacy/solver.py
Reason: LOW confidence SAF API merge — substantial changes on both sides
What was detected: SAF changed solver interface, user added custom optimization
What was attempted: Semantic merge using the selected comparison mode
What remains: User must manually review and test the merged code
```

> **Never report SUCCESS if unresolved migration conflicts remain.**

Also report:
- The exact Initial Read, Expanded Read, and Approved Write scopes used
- Every requested scope expansion and whether it was approved, rejected, or changed
- Every relevant path or behavior reported as `NOT INSPECTED`
- The selected comparison mode, old-template recovery attempts, and limitations caused by a missing baseline
- Which approval gates were granted or withheld
- Any non-SAF dependency exception and its approval
- End-to-end page, navigation, callback, and layout verification results
- Any behavior differences from the temporary original copy
- Verification status for each page, navigation link, callback, and layout comparison: `PASS`, `FAIL`, `NOT AVAILABLE`, or `BLOCKED BY ENVIRONMENT`