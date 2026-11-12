import math

import pytest

from tas_copilot_contracts import ToolCall, ToolResultStatus

from tas_psd_planner.copilot_plugin import run_tool
from tas_psd_planner.kinematics import (
    accessible_qe_boundary,
    analyzer_check,
    bragg_energy_floor,
    check_accessibility,
    energy_cut_limits,
    energy_transfer_range,
    get_tau,
    minimum_incident_energy,
    modvec,
    q_window_at_energy,
    reciprocal_lattice,
    scale_ei_limits,
)

# NCNR - BT7.json: A4Limits = [[4.9, 83.2], [120, 120]]
BT7_EI_LIMITS_PG002 = [4.9, 83.2]
BT7_A4_MAX_DEG = [120.0, 120.0]


def test_get_tau_matches_reslib_table():
    assert get_tau("PG(002)") == pytest.approx(1.87325)
    assert get_tau("Cu(220)") == pytest.approx(4.91593)
    assert get_tau(2.5) == pytest.approx(2.5)
    with pytest.raises(ValueError):
        get_tau("Si(111)")


def test_reciprocal_lattice_cubic():
    rlattice = reciprocal_lattice({"a": 2 * math.pi, "b": 2 * math.pi, "c": 2 * math.pi, "alpha": 90, "beta": 90, "gamma": 90})
    assert rlattice["a"] == pytest.approx(1.0)
    assert rlattice["b"] == pytest.approx(1.0)
    assert rlattice["c"] == pytest.approx(1.0)
    assert rlattice["alpha"] == pytest.approx(math.pi / 2)
    assert rlattice["unit_cell_volume"] == pytest.approx((2 * math.pi) ** 3)


def test_modvec_cubic():
    rlattice = reciprocal_lattice({"a": 2 * math.pi, "b": 2 * math.pi, "c": 2 * math.pi, "alpha": 90, "beta": 90, "gamma": 90})
    assert modvec(1.0, 1.0, 0.0, rlattice) == pytest.approx(math.sqrt(2.0))
    assert modvec(1.0, 0.0, 0.0, rlattice) == pytest.approx(1.0)


def test_bragg_energy_floor_pg002():
    # CheckAngles.m: min Ei from lattice spacing = 2.072*(tau/2)^2
    assert bragg_energy_floor("PG(002)") == pytest.approx(2.072 * (1.87325 / 2.0) ** 2)
    assert bragg_energy_floor("PG(002)") == pytest.approx(1.8177, rel=1e-3)


def test_minimum_incident_energy_uses_drum_or_bragg_floor():
    # BT7 PG(002): drum minimum 4.9 meV is above the 1.82 meV Bragg floor.
    assert minimum_incident_energy(BT7_EI_LIMITS_PG002, "PG(002)") == pytest.approx(4.9)
    # Synthetic drum minimum below the PG(004) Bragg floor: the floor wins.
    scaled = scale_ei_limits([1.0, 80.0], "PG(004)")
    assert scaled[0] == pytest.approx(1.0 * (3.7465 / 1.87325) ** 2)
    assert minimum_incident_energy(scaled, "PG(004)") == pytest.approx(bragg_energy_floor("PG(004)"))


def test_scale_ei_limits_identity_for_pg002():
    assert scale_ei_limits(BT7_EI_LIMITS_PG002, "PG(002)") == pytest.approx(BT7_EI_LIMITS_PG002)


def test_analyzer_check_flags_ef_below_bragg_floor():
    ok = analyzer_check(14.7, "PG(002)")
    assert ok["analyzer_ok"] is True
    bad = analyzer_check(1.0, "PG(002)")
    assert bad["analyzer_ok"] is False
    assert "analyzer_error" in bad


def test_energy_transfer_range_bt7():
    e_min, e_max = energy_transfer_range(4.9, 83.2, 14.7)
    assert e_min == pytest.approx(-9.8)
    assert e_max == pytest.approx(68.5)


def test_q_window_at_elastic_bt7():
    # Elastic, Ef = Ei = 14.7 meV, A4max = 120 deg, A4min = 5 deg.
    # Qmax = sqrt((29.4 - 2*14.7*cos(120 deg)) / 2.072) = sqrt(44.1 / 2.072)
    window = q_window_at_energy(0.0, 14.7, BT7_EI_LIMITS_PG002, BT7_A4_MAX_DEG, 5.0)
    assert window["q_max_inv_ang"] == pytest.approx(math.sqrt(44.1 / 2.072))
    assert window["q_max_inv_ang"] == pytest.approx(4.6134, rel=1e-4)
    expected_q_min = math.sqrt(29.4 * (1.0 - math.cos(math.radians(5.0))) / 2.072)
    assert window["q_min_inv_ang"] == pytest.approx(expected_q_min)


def test_q_window_outside_ei_table_is_nan():
    window = q_window_at_energy(100.0, 14.7, BT7_EI_LIMITS_PG002, BT7_A4_MAX_DEG, 5.0)
    assert math.isnan(window["q_max_inv_ang"])


def test_accessible_boundary_and_energy_cut_limits():
    boundary = accessible_qe_boundary(14.7, BT7_EI_LIMITS_PG002, BT7_A4_MAX_DEG, 5.0, "PG(002)")
    assert boundary["energy_transfer_mev"][0] == pytest.approx(4.9 - 14.7)
    assert boundary["energy_transfer_mev"][-1] == pytest.approx(83.2 - 14.7, abs=0.06)
    assert len(boundary["boundary_q_inv_ang"]) == 2 * len(boundary["energy_transfer_mev"])
    # A constant-Q cut inside the region crosses the boundary an even number of times.
    limits = energy_cut_limits(2.0, boundary["boundary_q_inv_ang"], boundary["boundary_e_mev"])
    assert len(limits) >= 2
    assert limits == sorted(limits)
    # A constant-Q cut far outside the region has no crossings.
    assert energy_cut_limits(50.0, boundary["boundary_q_inv_ang"], boundary["boundary_e_mev"]) == []


def test_check_accessibility_composite_elastic_point():
    report = check_accessibility(
        ef_mev=14.7,
        mono_reflection="PG(002)",
        ana_reflection="PG(002)",
        ei_limits_pg002_mev=BT7_EI_LIMITS_PG002,
        a4_max_limits_deg=BT7_A4_MAX_DEG,
        a4_min_deg=5.0,
        lattice={"a": 2 * math.pi, "b": 2 * math.pi, "c": 2 * math.pi, "alpha": 90, "beta": 90, "gamma": 90},
        q_points_rlu=[[1.0, 1.0, 0.0]],
        energy_transfers_mev=[0.0, 100.0],
    )
    assert report["parity_status"] == "ported_awaiting_matlab_fixture_check"
    assert report["energy_transfer_window_mev"] == pytest.approx([-9.8, 68.5])
    point = report["points"][0]
    assert point["q_inv_ang"] == pytest.approx(math.sqrt(2.0))
    elastic, far = point["energy_checks"]
    assert elastic["accessible"] is True
    assert far["within_energy_window"] is False
    assert far["accessible"] is False
    assert len(point["constant_q_energy_cut_limits_mev"]) >= 2


def test_check_accessibility_requires_lattice_for_rlu_points():
    with pytest.raises(ValueError):
        check_accessibility(
            ef_mev=14.7,
            mono_reflection="PG(002)",
            ana_reflection="PG(002)",
            ei_limits_pg002_mev=BT7_EI_LIMITS_PG002,
            a4_max_limits_deg=BT7_A4_MAX_DEG,
            a4_min_deg=5.0,
            q_points_rlu=[[1.0, 0.0, 0.0]],
        )


def test_plugin_runs_check_accessibility():
    result = run_tool(
        ToolCall(
            tool_namespace="tas.psd_planner",
            tool_name="check_accessibility",
            arguments={
                "ef_mev": 14.7,
                "mono_reflection": "PG(002)",
                "ana_reflection": "PG(002)",
                "ei_limits_pg002_mev": BT7_EI_LIMITS_PG002,
                "a4_max_limits_deg": BT7_A4_MAX_DEG,
                "a4_min_deg": 5.0,
                "q_moduli_inv_ang": [1.5],
                "energy_transfers_mev": [0.0],
            },
        )
    )
    assert result.status == ToolResultStatus.success
    accessibility = result.output["accessibility"]
    assert accessibility["points"][0]["energy_checks"][0]["accessible"] is True
    assert accessibility["safety_note"].startswith("Planning/simulation only")
    assert result.provenance[0].method == "explanner_kinematic_accessibility_port"
