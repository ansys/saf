# Code scanning alerts to Task issues

`code_scan_alert_to_user_story.py` fetches open GitHub Code Scanning alerts and
creates one GitHub issue for each alert at or above a configurable security
severity. Each issue is created with the **Task** issue type and the
`certification` label. The alert's security severity is included as its priority
in the issue description and, when available, is also written to the
organization's **Priority** issue field.

## Requirements

- [uv](https://docs.astral.sh/uv/)
- A `GITHUB_TOKEN` environment variable with permission to read code-scanning
  alerts and create issues in the target repository.
- The repository must have the **Task** issue type available.
- The token needs access to organization issue fields to set the optional
  **Priority** field. If the field is unavailable, inaccessible, or cannot
  represent the alert severity, the script warns and still creates the issue.

The script creates the repository's `security` label if it does not
already exist. For a single-select Priority field, the script maps Critical to
Urgent, and High/Medium/Low to the correspondingly named options. The default
severity-to-number mapping for a numeric Priority field is Critical=1, High=2,
Medium=3, Low=4.

## Usage

Set the token in PowerShell:

```powershell
$env:GITHUB_TOKEN = "github_pat_..."
```

Preview matching alerts without making changes:

```powershell
uv run scripts\code_scan_alert_to_user_story.py `
  --repository ansys/saf `
  --min-severity high `
  --dry-run
```

Create issues for Critical, High, and Medium alerts (the default threshold):

```powershell
uv run scripts\code_scan_alert_to_user_story.py --repository ansys/saf
```

Include Low severity alerts as well:

```powershell
uv run scripts\code_scan_alert_to_user_story.py `
  --repository ansys/saf `
  --min-severity low
```

Accepted `--min-severity` values are `critical`, `high`, `medium`, and `low`.
The threshold is inclusive: for example, `high` includes Critical and High
alerts. Only alerts that provide a recognized security severity are eligible.
Before creating an issue, the script checks open repository issues for the
alert marker or code-scanning alert link. If an open issue already references
that alert, it skips creating another one. Closed issues do not prevent a new
issue from being created.

Use `--priority-field FIELD_NAME` if the organization's issue field has a
different name. If setting the field fails, the script prints a warning and
continues; the severity remains in the issue description.
