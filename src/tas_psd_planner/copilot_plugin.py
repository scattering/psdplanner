"""TAS co-pilot plugin entry points for PSD planning support."""

from __future__ import annotations

_ARCHIVE_PATH = (
    "ExPlanner9"
)


def get_tool_specs():
    from tas_copilot_contracts import Availability, ImplementationType, PermissionLevel, SideEffectLevel, ToolSpec

    return [
        ToolSpec(
            name="summarize_facility",
            namespace="tas.psd_planner",
            version="0.1.0",
            description="Summarize TAS PSD planner facility definitions from ported ExPlanner source text.",
            input_schema={"type": "object", "required": ["facility_text"], "properties": {"facility_text": {"type": "string"}, "source_uri": {"type": "string"}}},
            output_schema={"type": "object"},
            side_effect_level=SideEffectLevel.planning,
            availability=Availability.available,
            implementation_type=ImplementationType.python_entrypoint,
            required_dependencies=["tas-psd-planner"],
            preconditions=["Facility definition text is supplied from a trusted local archive extraction step."],
            postconditions=["No files, hardware, or instrument state are modified."],
            provenance_policy="Record source archive path, facility definition source, and port status.",
            permissions_required=[PermissionLevel.planning_only],
            enabled_by_default=True,
            owner_repo="https://github.com/scattering/psdplanner",
            maintainer="William Ratcliff",
        ),
        ToolSpec(
            name="check_accessibility",
            namespace="tas.psd_planner",
            version="0.1.0",
            description=(
                "Kinematic accessibility check ported from Leland ExPlanner: reachable energy-transfer window, "
                "accessible |Q| window per energy from the facility A4-limit table, analyzer Bragg-floor check, "
                "and constant-Q energy-cut limits. Parity with MATLAB fixtures not yet demonstrated."
            ),
            input_schema={
                "type": "object",
                "required": ["ef_mev", "mono_reflection", "ana_reflection", "ei_limits_pg002_mev", "a4_max_limits_deg", "a4_min_deg"],
                "properties": {
                    "ef_mev": {"type": "number"},
                    "mono_reflection": {"type": "string"},
                    "ana_reflection": {"type": "string"},
                    "ei_limits_pg002_mev": {"type": "array", "items": {"type": "number"}},
                    "a4_max_limits_deg": {"type": "array", "items": {"type": "number"}},
                    "a4_min_deg": {"type": "number"},
                    "lattice": {
                        "type": "object",
                        "properties": {
                            "a": {"type": "number"},
                            "b": {"type": "number"},
                            "c": {"type": "number"},
                            "alpha": {"type": "number"},
                            "beta": {"type": "number"},
                            "gamma": {"type": "number"},
                        },
                    },
                    "q_points_rlu": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}},
                    "q_moduli_inv_ang": {"type": "array", "items": {"type": "number"}},
                    "energy_transfers_mev": {"type": "array", "items": {"type": "number"}},
                },
            },
            output_schema={"type": "object"},
            side_effect_level=SideEffectLevel.planning,
            availability=Availability.available,
            implementation_type=ImplementationType.python_entrypoint,
            required_dependencies=["tas-psd-planner"],
            preconditions=[
                "Facility Ei/A4 limit tables are supplied explicitly (e.g. from the ExPlanner facility JSON).",
                "The Ei limit table is given in the PG(002) basis as in the ExPlanner facility files.",
            ],
            postconditions=["No files, hardware, or instrument state are modified."],
            provenance_policy=(
                "Record ported MATLAB source files and parity status; outputs remain planning estimates until "
                "MATLAB fixture parity is demonstrated."
            ),
            permissions_required=[PermissionLevel.planning_only],
            enabled_by_default=True,
            owner_repo="https://github.com/scattering/psdplanner",
            maintainer="William Ratcliff",
        ),
    ]


def run_tool(call):
    from tas_copilot_contracts import ProvenanceRecord, ToolError, ToolResult, ToolResultStatus

    handlers = {
        ("tas.psd_planner", "summarize_facility"): _run_summarize_facility,
        ("tas.psd_planner", "check_accessibility"): _run_check_accessibility,
    }
    handler = handlers.get((call.tool_namespace, call.tool_name))
    if handler is None:
        return ToolResult(
            status=ToolResultStatus.validation_failed,
            errors=[ToolError(code="unknown_tool", message=f"Unknown PSD planner tool {call.tool_namespace}.{call.tool_name}")],
            tool_name=call.tool_name,
            tool_namespace=call.tool_namespace,
            tool_version="0.1.0",
        )
    try:
        return handler(call)
    except Exception as exc:
        return ToolResult(
            status=ToolResultStatus.error,
            errors=[ToolError(code=exc.__class__.__name__, message=str(exc))],
            tool_name=call.tool_name,
            tool_namespace=call.tool_namespace,
            tool_version="0.1.0",
        )


def _run_summarize_facility(call):
    from tas_copilot_contracts import ProvenanceRecord, ToolResult, ToolResultStatus

    from .facility import summarize_facility_text

    source_uri = call.arguments.get("source_uri")
    summary = summarize_facility_text(str(call.arguments.get("facility_text") or ""), source_uri=source_uri)
    return ToolResult(
        status=ToolResultStatus.success,
        output={"facility_summary": summary, "safety_note": "Planning/simulation only; not approved instrument operation."},
        provenance=[ProvenanceRecord(source_type="source_archive", source_id=source_uri, method="explanner_facility_summary")],
        tool_name="summarize_facility",
        tool_namespace="tas.psd_planner",
        tool_version="0.1.0",
    )


def _run_check_accessibility(call):
    from tas_copilot_contracts import ProvenanceRecord, ToolResult, ToolResultStatus

    from .kinematics import check_accessibility

    arguments = call.arguments
    report = check_accessibility(
        ef_mev=float(arguments["ef_mev"]),
        mono_reflection=str(arguments["mono_reflection"]),
        ana_reflection=str(arguments["ana_reflection"]),
        ei_limits_pg002_mev=[float(v) for v in arguments["ei_limits_pg002_mev"]],
        a4_max_limits_deg=[float(v) for v in arguments["a4_max_limits_deg"]],
        a4_min_deg=float(arguments["a4_min_deg"]),
        lattice=arguments.get("lattice"),
        q_points_rlu=arguments.get("q_points_rlu"),
        q_moduli_inv_ang=arguments.get("q_moduli_inv_ang"),
        energy_transfers_mev=arguments.get("energy_transfers_mev"),
    )
    return ToolResult(
        status=ToolResultStatus.success,
        output={"accessibility": report},
        provenance=[
            ProvenanceRecord(
                source_type="source_archive",
                source_id=_ARCHIVE_PATH,
                method="explanner_kinematic_accessibility_port",
            )
        ],
        tool_name="check_accessibility",
        tool_namespace="tas.psd_planner",
        tool_version="0.1.0",
    )
