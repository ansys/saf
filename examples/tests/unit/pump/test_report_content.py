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

import io
from pathlib import Path
from unittest.mock import MagicMock
import zipfile

from saf.solutions.examples.solution.logic.pump.report import builder
from saf.solutions.examples.solution.logic.pump.report.content import (
    PumpReportData,
    assumption_rows,
    convergence_series,
    convergence_summary,
    html_table,
    key_result_rows,
    operating_point_rows,
    secondary_result_rows,
)
from saf.solutions.examples.solution.logic.pump.report.settings import ReportSettings


def _data(**overrides) -> PumpReportData:
    values = dict(
        project_name="Duty point A",
        impeller_speed_rpm=1450.0,
        mass_flow_rate=90.0,
        iteration_count=200,
        time_step_scale_factor=10.0,
        processor_count=4,
        converged=True,
        pump_head_m=20.123,
        hydraulic_efficiency=0.8234,
        shaft_power_w=21500.0,
        pressure_rise_pa=197000.0,
        blade_torque_nm=141.5,
        volumetric_flow_m3h=324.58,
        inlet_total_pressure_pa=-100.0,
        outlet_total_pressure_pa=196900.0,
        blade_pressure_pa=150000.0,
    )
    values.update(overrides)
    return PumpReportData(**values)


# ------------------------------------------------------------------------------------- content ----


def test_operating_point_rows_list_every_input_with_its_unit():
    rows = operating_point_rows(_data())
    assert rows[0] == ("Impeller speed", "1450", "rpm")
    assert rows[1] == ("Mass flow rate", "90.00", "kg/s")
    assert [row[0] for row in rows[2:]] == ["Iteration count", "Pseudo time step scale factor", "Processor count"]


def test_key_results_report_efficiency_in_percent_and_power_in_kilowatts():
    assert key_result_rows(_data()) == [
        ("Pump head", "20.12", "m"),
        ("Hydraulic efficiency", "82.3", "%"),
        ("Shaft power", "21.50", "kW"),
    ]


def test_secondary_results_report_the_pressure_rise_in_kilopascals():
    rows = secondary_result_rows(_data())
    assert rows[0] == ("Total pressure rise", "197.00", "kPa")
    assert len(rows) == 6


def test_assumptions_state_the_fluid_properties_used_by_the_solver():
    text = " ".join(assumption for _, assumption in assumption_rows())
    assert "998.2 kg/m³" in text
    assert "0.001002" in text
    assert "frozen rotor" in text


def test_convergence_summary_warns_when_the_solve_did_not_converge():
    assert "Converged." in convergence_summary(_data(converged=True))
    assert "Not converged." in convergence_summary(_data(converged=False))


def test_html_table_escapes_its_cells():
    rendered = html_table(("Project",), [("<script>alert(1)</script>",)])
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered


_HISTORY = (
    {"iteration": 2, "head": 21.0, "outlet_total_pressure": 197000.0},
    {"iteration": 1, "head": 25.0, "outlet_total_pressure": 230000.0},
)


def test_convergence_series_orders_the_samples_by_iteration():
    series = convergence_series(_data(convergence_history=_HISTORY))
    assert series.iterations == [1.0, 2.0]
    assert series.head_m == [25.0, 21.0]
    assert series.outlet_total_pressure_pa == [230000.0, 197000.0]


def test_convergence_series_is_absent_without_a_history():
    assert convergence_series(_data()) is None


# ------------------------------------------------------------------------------------- settings ----


def test_report_is_unavailable_without_an_adr_installation():
    assert ReportSettings(adr_installation_directory="").is_available is False


def test_adr_database_defaults_next_to_the_glow_project_files(tmp_path):
    settings = ReportSettings(glow_project_files_directory=str(tmp_path / "projects"))
    assert settings.db_directory == tmp_path / "adr" / "report_data"
    assert settings.media_directory == tmp_path / "adr" / "report_data" / "media"
    assert settings.static_directory == tmp_path / "adr" / "static_assets"


# -------------------------------------------------------------------------------------- builder ----


def test_create_items_tags_every_item_with_the_project_tag(tmp_path):
    adr = MagicMock()
    builder.create_items(adr, _data(), tmp_path / "contour.png", "pump-report=abc")

    names = [call.kwargs["name"] for call in adr.create_item.call_args_list]
    assert names == [
        "report-details",
        "problem-description",
        "operating-point",
        "assumptions",
        "convergence",
        "key-results",
        "secondary-results",
        "pressure-contour",
    ]
    assert all(call.kwargs["tags"].endswith(" pump-report=abc") for call in adr.create_item.call_args_list)


def test_create_items_plots_the_convergence_history_against_the_iteration(tmp_path):
    adr = MagicMock()
    builder.create_items(adr, _data(convergence_history=_HISTORY), tmp_path / "contour.png", "pump-report=abc")

    calls = {call.kwargs["name"]: call for call in adr.create_item.call_args_list}
    names = list(calls)
    assert names[names.index("convergence") + 1 : names.index("key-results")] == [
        "convergence-head",
        "convergence-outlet-pressure",
    ]
    assert calls["convergence-head"].kwargs["content"].tolist() == [[1.0, 2.0], [25.0, 21.0]]
    assert calls["convergence-outlet-pressure"].kwargs["content"].tolist() == [[1.0, 2.0], [230000.0, 197000.0]]
    head_plot = adr.create_item.return_value
    assert head_plot.plot == "line"
    assert head_plot.xaxis == "Iteration"
    head_plot.save.assert_called()


def test_ensure_template_reuses_an_existing_template():
    adr = MagicMock()
    existing = MagicMock()
    adr.query.return_value = [existing]
    assert builder.ensure_template(adr) is existing
    adr.create_template.assert_not_called()


def test_render_report_keeps_the_html_when_the_pdf_export_fails(monkeypatch, tmp_path):
    adr = MagicMock()

    def export_html(directory, filename, item_filter, name):
        (Path(directory) / filename).write_text("<html>exported</html>")

    adr.export_report_as_html.side_effect = export_html
    adr.export_report_as_pdf.side_effect = RuntimeError("no browser")
    template = MagicMock()
    template.render.return_value = "<html>rendered</html>"
    monkeypatch.setattr(builder, "get_adr", lambda settings: adr)
    monkeypatch.setattr(builder, "ensure_template", lambda adr: template)

    report = builder.render_report(ReportSettings(), _data(), tmp_path / "contour.png", "pump-report=abc", tmp_path)

    assert report.html == "<html>rendered</html>"
    assert report.pdf_path is None
    with zipfile.ZipFile(io.BytesIO(report.html_zip)) as archive:
        assert archive.read(builder.REPORT_HTML_FILE_NAME) == b"<html>exported</html>"
    template.render.assert_called_once_with(context={}, item_filter="A|i_tags|cont|pump-report=abc;")
