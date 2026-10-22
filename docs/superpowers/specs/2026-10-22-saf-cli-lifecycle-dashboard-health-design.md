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

The shared-solution CI failures have different evidence: Linux failed while
downloading a package (`IncompleteRead`), while Windows timed out creating a
project with `POST /projects`. The equivalent Windows shared test passed in a
local Python 3.11 run. These failures do not currently establish a common
code defect and will be rerun after the branch update.

## Design

Update the lifecycle health check to model the dashboard-backed portal flow:

- Do not require a separate Portal listener when the generated solution uses
  the Projects Dashboard.
- Verify that the dashboard route is served from the solution UI, as well as
  verifying the API and generated project UI used by the lifecycle test.
- Keep the existing separate-Portal health check available for callers that
  use a standalone Portal.
- Add focused regression coverage for the dashboard-backed flow; do not
  change orchestrator runtime behavior.

The implementation should use the repository's existing URL helpers and test
patterns, keeping the distinction between a Portal URL and a dashboard route
explicit. Existing health checks for other callers should remain unchanged.

## Out of scope

Do not add broad retries or longer timeouts for the shared-solution test
failures based only on this run. Rerun those checks after the branch update;
investigate any reproducible application failure separately. Do not change the
orchestrator to start an extra Portal when the dashboard is configured.

## Validation

- Add a regression test that fails when the dashboard-backed lifecycle check
  probes the unused Portal port or omits the dashboard route.
- Run the focused SAF-CLI tests covering the lifecycle health check.
- Rerun the four requested Python 3.12 Linux and Windows shared-solution and
  lifecycle CI jobs after pushing the updated branch.
