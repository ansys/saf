<!--
SPDX-FileCopyrightText: Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
SPDX-License-Identifier: Apache-2.0
-->

# SAF-CLI lifecycle health check for the Projects Dashboard

## Problem

The minimal solution template now includes the Projects Dashboard. When the
orchestrator runs a solution with portal mode enabled and the dashboard is
installed, it serves the dashboard from the solution UI and does not start a
separate SAF Portal process. The SAF-CLI lifecycle test still passes
`PORTAL_UI_PORT` to its health-check helper, which probes that unused port and
fails on both Linux and Windows.

The initial shared-solution failures were inconclusive: Linux failed while
downloading a package (`IncompleteRead`), while Windows timed out creating a
project with `POST /projects`. After the branch update, both Linux checks
passed, but both Windows checks reproduced the same `httpx2.ReadTimeout` in
the orchestrator's project-creation request. The API had started and passed
its health check before that request.

## Design

Update the lifecycle health check to model the dashboard-backed portal flow:

- Do not require a separate Portal listener when the generated solution uses
  the Projects Dashboard.
- Verify that the dashboard route is served from the solution UI, as well as
  verifying the API and generated project UI used by the lifecycle test.
- Keep the existing separate-Portal health check available for callers that
  use a standalone Portal.
- Add focused regression coverage for the dashboard-backed flow; do not
  change the dashboard or Portal startup behavior.
- Set a bounded 60-second timeout on the orchestrator's `POST /projects`
  request only. Do not retry the POST because project creation is not
  idempotent; leave other requests and client defaults unchanged.

The implementation should use the repository's existing URL helpers and test
patterns, keeping the distinction between a Portal URL and a dashboard route
explicit. Existing health checks for other callers should remain unchanged.

## Out of scope

Do not add broad retries, global timeout changes, or an extra Portal when the
dashboard is configured. Keep the timeout adjustment limited to the
reproduced project-creation request.

## Validation

- Add a regression test that fails when the dashboard-backed lifecycle check
  probes the unused Portal port or omits the dashboard route.
- Add an orchestrator unit test that verifies project creation sends the
  bounded request timeout exactly once.
- Run the focused SAF-CLI tests covering the lifecycle health check.
- Run the focused orchestrator project-creation test.
- Rerun the four requested Python 3.12 Linux and Windows shared-solution and
  lifecycle CI jobs after pushing the updated branch.
