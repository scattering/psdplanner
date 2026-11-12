from tas_copilot_contracts import ToolCall, ToolResultStatus

from tas_psd_planner.copilot_plugin import get_tool_specs, run_tool
from tas_psd_planner.facility import summarize_facility_text


FACILITY_TEXT = """
{
  "dstruct": {
    "Facility": "NCNR",
    "Instrument": "BT7",
    "Type": "Thermal",
    "LastUpdate": "February, 2012",
    "A4Limits": [[4.9,83.2],[120,120]],
    "Monochromator": {"M1": {"Name": "PG(002)"}, "M2": {"Name": "PG(004)"}},
    "Analyzer": {"A1": {"Name": "PG(002)"}},
    "GMCollimator": {"C1": {"Name": "Soller-10'"}, "C4": {"Name": "Open"}},
    "UpstreamFilter": {"F1": {"Name": "PG"}, "F2": {"Name": "None"}}
  }
}
"""


def test_summarize_facility_text_extracts_planner_fields():
    summary = summarize_facility_text(FACILITY_TEXT, source_uri="fixture")

    assert summary["facility"] == "NCNR"
    assert summary["instrument"] == "BT7"
    assert "PG(002)" in summary["monochromators"]
    assert "Open" in summary["collimators"]
    assert summary["source_uri"] == "fixture"


def test_plugin_exposes_planning_only_tools():
    specs = get_tool_specs()
    assert [(spec.namespace, spec.name) for spec in specs] == [
        ("tas.psd_planner", "summarize_facility"),
        ("tas.psd_planner", "check_accessibility"),
    ]
    for spec in specs:
        assert spec.permissions_required[0].value == "planning_only"


def test_plugin_runs_facility_summary():
    result = run_tool(
        ToolCall(
            tool_namespace="tas.psd_planner",
            tool_name="summarize_facility",
            arguments={"facility_text": FACILITY_TEXT, "source_uri": "fixture"},
        )
    )

    assert result.status == ToolResultStatus.success
    assert result.output["facility_summary"]["instrument"] == "BT7"
    assert "Planning/simulation only" in result.output["safety_note"]
