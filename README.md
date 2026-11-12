# TAS PSD Planner

Python planning boundary for selected PSD/experiment-planning algorithms from Leland ExPlanner and related TAS PSD MATLAB archives.

This package does not port the full planner. It provides:

- source provenance for the MATLAB archive
- facility-definition extraction for BT-7/SPINS-style planner JSON files
- a kinematic accessibility port (`kinematics.py`) of the ExPlanner
  accessible-Q/E logic: monochromator/analyzer Bragg floors, the reachable
  energy-transfer window, accessible |Q| windows from the facility A4-limit
  table, and constant-Q energy-cut limits
- a read-only/planning-only TAS co-pilot plugin
- explicit unavailable/planning notes for algorithms that still need numerical MATLAB fixtures

Primary source archive (historically distributed as `EXPPlanner.zip`):

`ExPlanner9`

MATLAB source files ported in the kinematics slice:

- `PlannerFunctions/CheckAngles.m` (Bragg floors, energy-window check)
- `PlannerFunctions/AccessibleQ_Plot.m` (Q window at fixed E from the A4-limit table)
- `PlannerFunctions/AccessibleE_Plot.m` (accessible-region boundary, constant-Q cut limits)
- `PlannerFunctions/Hand2Num.m` (unit conventions for the A4Limits table)
- `PlannerFunctions/ExtractInstrumentParameters.m` (PG(002)-basis Ei scale factor)
- `ResLib3.4c/GetTau.m`, `star.m`, `scalar.m`/`modvec.m` (tau table, reciprocal lattice, |Q|)

Identified but not yet ported:

- `PlannerFunctions/ResolutionCalculation.m` / `ResMat_ExPlanner.m` (ResLib-based; overlaps the rescalculator plugin)
- `PSD_Planner1/2` and `RowlandDesign_Planner` (PSD coverage / Rowland geometry)
- `Rmon_Calc.m`, `Monitor_to_Flux.m` (monitor-to-flux normalization)

Parity status: the kinematics port is line-faithful to the MATLAB sources and
covered by hand-computed unit tests, but numerical parity against
MATLAB-generated fixtures has not yet been demonstrated. Outputs carry
`parity_status = "ported_awaiting_matlab_fixture_check"` until ExPlanner
reference fixtures are added.

## Plugin

- namespace: `tas.psd_planner`
- tools: `summarize_facility`, `check_accessibility`
- permission: `planning_only`

`check_accessibility` takes the facility limit tables explicitly (Ei row in
the PG(002) basis, max-A4 row in degrees, both as in the ExPlanner facility
JSON files), plus `ef_mev`, monochromator/analyzer reflections, an A4 minimum,
and optional lattice + (H,K,L)/|Q|/energy-transfer targets.

This is for planning/simulation support only. It is not approved instrument operation.

## Reproducibility Tests

Install the shared contracts from the
[TASCopilot paper repository](https://github.com/scattering/tascopilot-paper)
and this package into a Python 3.11 or newer environment:

```sh
TASCOPILOT_PAPER=/absolute/path/to/tascopilot-paper
python -m pip install -e "$TASCOPILOT_PAPER/packages/tas_copilot_contracts"
python -m pip install -e . pytest
python -m pytest -q -rs
```

Tests use local fixtures. Optional upstream runtimes or explicitly supplied
archive fixtures are reported as skipped when unavailable. No instrument
connection is required. No full papers, private corpus, or development
handoff documents are included.
