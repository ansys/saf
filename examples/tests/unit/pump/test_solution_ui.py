# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0

#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import inspect
import json
from types import SimpleNamespace

from dash.exceptions import PreventUpdate
from dash.testing import ignore_register_page
from dash_extensions.enrich import no_update
import dash_mantine_components as dmc
import pytest

from saf.solutions.examples.solution.definition import ExamplesSolution
from saf.solutions.examples.solution.logic.pump.constants import PROCESSOR_COUNT_RANGE
from saf.solutions.examples.ui.pages.pump import shell_notifications

with ignore_register_page():
    from saf.solutions.examples.ui.pages.pump import pump_about_page as about_page
    from saf.solutions.examples.ui.pages.pump import pump_model_setup_page as model_setup_page
    from saf.solutions.examples.ui.pages.pump import pump_operating_point_page as operating_point_page


# ------------------------------------------------------------------------------------ about page ----


def test_about_layout_takes_no_arguments_so_the_page_needs_no_project():
    # The page is static: a layout that accepted a project would mean it reads a step.
    assert list(inspect.signature(about_page.layout).parameters) == []


def test_about_layout_opens_with_plain_language_for_a_non_expert():
    rendered = str(about_page.layout())
    assert "What this application is for" in rendered
    assert "how does the pump perform" in rendered


def test_about_layout_states_its_purpose_in_a_single_sentence():
    # The page has to fit on a screen, so the opening is one sentence and nothing more.
    rendered = str(about_page.layout())
    assert "A centrifugal pump raises the pressure of a liquid" not in rendered


def test_about_layout_names_the_inputs_the_user_supplies():
    rendered = str(about_page.layout())
    for quantity in ("Impeller speed", "Flow rate"):
        assert quantity in rendered


def test_about_layout_lists_the_headline_outputs():
    rendered = str(about_page.layout())
    for quantity in ("Pump head", "Efficiency", "Shaft power"):
        assert quantity in rendered


def test_about_layout_groups_the_overview_in_an_accordion_open_by_default():
    # The overview is long enough to want folding away, but a first-time visitor must see
    # it without having to discover the control.
    accordion = next(child for child in about_page.layout().children if isinstance(child, dmc.Accordion))
    assert accordion.value == "about"
    assert "About this app" in str(accordion)
    for heading in ("What this application is for", "What you give it", "What you get back", "How to use it"):
        assert heading in str(accordion)


def test_about_layout_lists_the_input_defaults():
    rendered = str(about_page.layout())
    assert "1450" in rendered
    assert "90" in rendered


def test_expert_details_hide_the_assumptions_and_equations_behind_an_accordion():
    # The depth has to be present but out of the way for a first-time user.
    rendered = str(about_page.expert_details())
    assert "Modelling assumptions" in rendered
    assert "Governing equations" in rendered
    assert "Accordion" in rendered


def test_expert_details_describe_the_two_workflow_steps():
    rendered = str(about_page.expert_details())
    assert "build_case" in rendered
    assert "run_simulation" in rendered


def test_expert_details_explain_the_frozen_rotor_limitation():
    assert "frozen rotor" in str(about_page.expert_details()).lower()
    assert "volute tongue" in str(about_page.expert_details())


def test_equations_avoid_macros_the_bundled_mathjax_cannot_render():
    # Dash registers ``boldsymbol`` for CDN autoload only, so offline it renders as raw text.
    assert "\\boldsymbol" not in about_page.EQUATIONS


def test_go_to_model_setup_does_nothing_until_the_button_is_clicked():
    # The page is mounted by the shell's routing callback, so this fires with n_clicks=None.
    assert about_page.go_to_model_setup(None, "a-project") is no_update


def test_go_to_model_setup_does_nothing_without_a_project():
    assert about_page.go_to_model_setup(1, None) is no_update


# ------------------------------------------------------------------------------ model setup page ----


def test_model_setup_results_panel_is_a_placeholder_before_the_case_is_built(
    client_project: ExamplesSolution,
):
    rendered = str(model_setup_page.results_panel(client_project.steps.pump_model_setup_step))
    assert "No case yet" in rendered
    assert "Mesh preview" not in rendered


def test_model_setup_notification_copy_targets_its_own_toast():
    assert shell_notifications.BUILD_CASE_NOTIFICATION.notification_id == "build-case-notification"


def test_processor_count_limit_follows_the_machine_on_the_desktop_deployment(monkeypatch):
    # Fluent runs on this machine, so offering more processes than cores only slows it down.
    monkeypatch.setenv("GLOW_DEPLOYMENT", "Desktop")
    monkeypatch.setattr(model_setup_page.os, "cpu_count", lambda: 8)
    assert model_setup_page.processor_count_limit() == 8


def test_processor_count_limit_stays_inside_the_declared_range(monkeypatch):
    monkeypatch.setenv("GLOW_DEPLOYMENT", "Desktop")
    monkeypatch.setattr(model_setup_page.os, "cpu_count", lambda: 512)
    assert model_setup_page.processor_count_limit() == PROCESSOR_COUNT_RANGE[1]

    monkeypatch.setattr(model_setup_page.os, "cpu_count", lambda: None)
    assert model_setup_page.processor_count_limit() == PROCESSOR_COUNT_RANGE[0]


def test_processor_count_limit_keeps_the_full_range_off_the_desktop(monkeypatch):
    # Any other deployment solves elsewhere, where the local core count means nothing.
    monkeypatch.setenv("GLOW_DEPLOYMENT", "DockerCompose")
    monkeypatch.setattr(model_setup_page.os, "cpu_count", lambda: 2)
    assert model_setup_page.processor_count_limit() == PROCESSOR_COUNT_RANGE[1]


# -------------------------------------------------------------------------- operating point page ----


def test_operating_point_parameters_table_names_every_input():
    # The sketch is only useful if its legend matches the fields on the operating point card.
    named = {row[1] for row in operating_point_page._PARAMETER_ROWS}
    assert named == {"mass_flow_rate", "impeller_speed_rpm"}


def test_operating_point_parameters_table_gives_a_unit_and_an_effect_for_every_row():
    for row in operating_point_page._PARAMETER_ROWS:
        assert len(row) == 4
        assert all(str(cell).strip() for cell in row)


def test_flow_rate_hint_converts_mass_flow_to_cubic_metres_per_hour():
    assert operating_point_page.flow_rate_hint(90.0) == pytest.approx(324.58, abs=0.01)


def test_flow_rate_hint_of_zero_is_zero():
    assert operating_point_page.flow_rate_hint(0.0) == 0.0


def test_operating_point_results_panel_is_a_placeholder_before_a_run(
    client_project: ExamplesSolution,
):
    rendered = str(operating_point_page.results_panel(client_project.steps.pump_solve_step))
    assert "No results yet" in rendered
    assert "Pump head" not in rendered


def test_operating_point_notification_copy_targets_its_own_toast():
    assert shell_notifications.RUN_SIMULATION_NOTIFICATION.notification_id == "run-simulation-notification"


def test_update_flow_rate_hint_blanks_an_empty_input():
    assert operating_point_page.update_flow_rate_hint(None) == ""


def test_convergence_card_marks_the_curve_as_live_while_the_solve_runs():
    history = [{"iteration": 1, "head": 10.0, "outlet_total_pressure": 1000.0}]
    assert "Live" in str(operating_point_page.convergence_card(history, live=True))
    assert "Live" not in str(operating_point_page.convergence_card(history))


def test_live_convergence_stays_empty_until_fluent_has_written_a_sample():
    # Nothing has been written yet in the first seconds of a run.
    empty = SimpleNamespace(convergence_history=[])
    assert operating_point_page.live_convergence(empty, is_running=True).children is None
    assert operating_point_page.live_convergence(empty, is_running=False).children is None


def test_live_convergence_draws_the_partial_curve_of_a_running_solve():
    step = SimpleNamespace(convergence_history=[{"iteration": 1, "head": 10.0, "outlet_total_pressure": 1.0}])
    assert "Live" in str(operating_point_page.live_convergence(step, is_running=True))


def test_live_convergence_keeps_the_curve_after_the_run_without_the_live_badge():
    step = SimpleNamespace(convergence_history=[{"iteration": 1, "head": 10.0, "outlet_total_pressure": 1.0}])
    rendered = str(operating_point_page.live_convergence(step, is_running=False))
    assert "Convergence" in rendered
    assert "Live" not in rendered


def test_on_run_simulation_history_draws_the_curve_carried_by_the_event():
    message = {"data": json.dumps({"history": [{"iteration": 1, "head": 10.0, "outlet_total_pressure": 1000.0}]})}
    assert "Live" in str(operating_point_page.on_run_simulation_history(message))


def test_on_run_simulation_history_ignores_an_empty_curve():
    with pytest.raises(PreventUpdate):
        operating_point_page.on_run_simulation_history({"data": json.dumps({"history": []})})
