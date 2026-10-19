# Pump

## Instructions

This solution simulates a centrifugal water pump (impeller + volute) with Ansys Fluent and reports its
performance at one operating point: pump head, hydraulic efficiency and shaft power.

Physics, fixed by the solution and not configurable:

- Steady-state, frozen-rotor (MRF) model of the impeller coupled to the volute through a turbo interface.
- k-ω SST turbulence. Liquid water, constant density 998.2 kg/m³, viscosity 0.001002 kg/(m·s).
- Inlet at -100 Pa gauge (a pressure datum only: head, torque, power and efficiency do not depend on it).
- The meshes are the PyFluent `pump-volute` example; they are downloaded by `build_case`. Users cannot
  upload their own geometry or mesh.

Steps:

- `setup_step`: builds the Fluent case once per project. Input: `processor_count` (int, 1 to 32, default 4).
- `solve_step`: solves the case at one operating point. Inputs (with allowed ranges and defaults):
  - `impeller_speed_rpm` (float, 100 to 3000 rpm, default 1450)
  - `mass_flow_rate` (float, 1 to 300 kg/s, default 90)
  - `iteration_count` (int, 1 to 5000, default 200)
  - `time_step_scale_factor` (float, 0.1 to 100, default 10): pseudo-time step scale factor.
    Lower it if the solve does not converge.
- `report_step`: builds an engineering report of the last solve with Ansys Dynamic Reporting (ADR).

Result fields on `solve_step` (they describe the last successful `run_simulation`, not the current inputs):

- `pump_head_m` (m), `hydraulic_efficiency` (a fraction from 0 to 1, not a percentage), `shaft_power_w` (W).
- `pressure_rise_pa`, `inlet_total_pressure_pa`, `outlet_total_pressure_pa`, `blade_pressure_pa` (Pa, gauge),
  `blade_torque_nm` (N·m), `volumetric_flow_m3h` (m³/h).
- `converged` (bool): True when the pump head varied by less than 0.5 % over the last 10 % of the
  iterations. Always state the convergence status together with the results; if it is False, say the
  results are not reliable and suggest more iterations or a lower `time_step_scale_factor`.
- `convergence_history`: list of `{iteration, head, outlet_total_pressure}` samples (m and Pa).
- `contour_image`: PNG of the static pressure on the impeller mid-plane.

Constraints:

- `build_case`, `run_simulation` and `generate_report` are long-running and launch Fluent or ADR. They take
  minutes. Never start one while the same transaction is still running on the project.
- Input ranges are validated when a transaction runs, not when the field is set. Check the ranges above
  before calling `set_fields`, so an out-of-range value does not waste a run.
- Only download the small artefacts: `setup_step.mesh_image`, `solve_step.contour_image` and, if needed,
  `report_step.report_pdf`. Do not download the Fluent case and data files (`case_file`, `data_file`,
  `solved_case_file`, `solved_data_file`), the 3D scenes (`scene_file`, `solved_scene_file`) or
  `report_step.report_html_file`: they are large.
- Ignore the 3D viewer transactions: `setup_step__start_visor`, `setup_step__update_scene`,
  `setup_step__show_scene`, `setup_step__shutdown_visor`, `setup_step__prepare_scene`,
  `solve_step__prepare_solved_scene` and `solve_step__show_solved_scene`. They drive the interactive
  viewer of the web UI and are not needed to obtain results.
- `progress_stage`, `progress_fraction` and `log_text` report the progress and Fluent transcript of the
  running transaction. Read `log_text` to explain a failure.

## Workflow

1. Create a project, or reuse an existing one. A project holds one pump case and the results of its last
   operating point.
2. Optional: set `processor_count` on `setup_step`.
3. Run `setup_step__build_case` and wait for it to finish. It builds the case that every operating point
   reuses, so run it only once per project. Check that `setup_step.case_file` is set afterwards.
4. Set the operating point on `solve_step`: `impeller_speed_rpm`, `mass_flow_rate` and, if needed,
   `iteration_count` and `time_step_scale_factor`.
5. Run `solve_step__run_simulation` and wait for it to finish. It fails if step 3 has not completed.
6. Read the results from `solve_step` with `get_fields`: at least `pump_head_m`, `hydraulic_efficiency`,
   `shaft_power_w` and `converged`. Present the efficiency as a percentage.
7. Optional: download `solve_step.contour_image` to show the static pressure field.
8. Optional: run `report_step__generate_report` (pass the project display name as `project_name`) and wait
   for it to finish. It fails if no simulation has run, or if ADR is not installed on the server.
   Afterwards, `report_step.report_html_content` holds the report as HTML and `report_step.report_pdf`
   holds the PDF, when the server can export PDFs.
9. To evaluate another operating point, repeat steps 4 to 8 in the same project. Each run replaces the
   previous results and makes the existing report outdated. To compare operating points, record each
   result before starting the next run, or use one project per operating point (each needs its own
   `build_case`).

