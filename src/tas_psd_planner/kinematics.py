"""Kinematic accessibility port from Leland ExPlanner (MATLAB).

Direct Python port of the kinematic-accessibility logic in the ExPlanner9
MATLAB archive. Nothing here is re-derived; every function cites the MATLAB
source file it was ported from. Source archive:

`ExPlanner9`

Ported source files:

- ``ResLib3.4c/GetTau.m`` (A. Zheludev, ResLib v.3.4) -> :func:`get_tau`
- ``ResLib3.4c/star.m`` -> :func:`reciprocal_lattice`
- ``ResLib3.4c/scalar.m`` / ``modvec.m`` -> :func:`modvec`
- ``PlannerFunctions/Hand2Num.m`` (lines 24-37) -> unit conventions:
  the facility ``A4Limits`` table row 1 is an Ei list in meV defined for
  PG(002); row 2 is the matching max-A4 list in degrees; the user A4 minimum
  is supplied in degrees.
- ``PlannerFunctions/ExtractInstrumentParameters.m`` (Ei scale factor) ->
  :func:`scale_ei_limits`
- ``PlannerFunctions/CheckAngles.m`` -> :func:`minimum_incident_energy`,
  :func:`bragg_energy_floor`, :func:`energy_transfer_range`
- ``PlannerFunctions/AccessibleQ_Plot.m`` (Qmax/Qmin at fixed E) ->
  :func:`q_window_at_energy`
- ``PlannerFunctions/AccessibleE_Plot.m`` (accessible-region boundary and
  constant-Q energy-cut crossings) -> :func:`accessible_qe_boundary`,
  :func:`energy_cut_limits`

Parity status: the algorithms are line-faithful ports, but numerical parity
against MATLAB-generated fixtures has not yet been demonstrated (no MATLAB
runtime in this environment). Per repository policy, outputs carry
``parity_status = "ported_awaiting_matlab_fixture_check"`` until reference
fixtures from the original ExPlanner are added.

Planning/simulation use only. This module never issues instrument commands.
"""

from __future__ import annotations

import math
from typing import Any

# E (meV) = 2.072 * k^2 (Angstrom^-2). Constant as written throughout the
# ExPlanner MATLAB sources (CheckAngles.m, AccessibleQ_Plot.m, AccessibleE_Plot.m).
ENERGY_CONSTANT_MEV_ANG2 = 2.072

# AccessibleE_Plot.m: interpEi = min_Ei:0.05:max(hEiLimits)
DEFAULT_EI_GRID_STEP_MEV = 0.05

# ResLib3.4c/GetTau.m tau-values for common monochromator crystals.
_TAU_TABLE = {
    "pg(002)": 1.87325,
    "pg(004)": 3.74650,
    "ge(111)": 1.92366,
    "ge(220)": 3.14131,
    "ge(311)": 3.68351,
    "be(002)": 3.50702,
    "pg(110)": 5.49806,
    "cu(220)": 4.91593,
}

PARITY_STATUS = "ported_awaiting_matlab_fixture_check"


def get_tau(reflection: str | float) -> float:
    """Port of ``ResLib3.4c/GetTau.m``: tau (|G|, Angstrom^-1) for common crystals."""
    if isinstance(reflection, (int, float)):
        return float(reflection)
    key = str(reflection).strip().lower()
    if key not in _TAU_TABLE:
        raise ValueError(f"Unknown monochromator/analyzer reflection {reflection!r}; known: {sorted(_TAU_TABLE)}")
    return _TAU_TABLE[key]


def reciprocal_lattice(lattice: dict[str, float]) -> dict[str, float]:
    """Port of ``ResLib3.4c/star.m``: reciprocal lattice parameters.

    ``lattice`` uses Angstroms and degrees (``GetLattice.m`` converts degrees
    to radians before calling ``star.m``; that conversion is folded in here).
    Returned angles are in radians, as used directly by ``scalar.m``.
    """
    a, b, c = float(lattice["a"]), float(lattice["b"]), float(lattice["c"])
    alpha = math.radians(float(lattice["alpha"]))
    beta = math.radians(float(lattice["beta"]))
    gamma = math.radians(float(lattice["gamma"]))
    volume = (
        2.0
        * a
        * b
        * c
        * math.sqrt(
            math.sin((alpha + beta + gamma) / 2.0)
            * math.sin((-alpha + beta + gamma) / 2.0)
            * math.sin((alpha - beta + gamma) / 2.0)
            * math.sin((alpha + beta - gamma) / 2.0)
        )
    )
    return {
        "a": 2.0 * math.pi * b * c * math.sin(alpha) / volume,
        "b": 2.0 * math.pi * a * c * math.sin(beta) / volume,
        "c": 2.0 * math.pi * b * a * math.sin(gamma) / volume,
        "alpha": math.acos((math.cos(beta) * math.cos(gamma) - math.cos(alpha)) / (math.sin(beta) * math.sin(gamma))),
        "beta": math.acos((math.cos(alpha) * math.cos(gamma) - math.cos(beta)) / (math.sin(alpha) * math.sin(gamma))),
        "gamma": math.acos((math.cos(alpha) * math.cos(beta) - math.cos(gamma)) / (math.sin(alpha) * math.sin(beta))),
        "unit_cell_volume": volume,
    }


def modvec(x: float, y: float, z: float, rlattice: dict[str, float]) -> float:
    """Port of ``ResLib3.4c/modvec.m`` + ``scalar.m``: |Q| (Angstrom^-1) of an (H,K,L)."""
    s = (
        x * x * rlattice["a"] ** 2
        + y * y * rlattice["b"] ** 2
        + z * z * rlattice["c"] ** 2
        + 2.0 * x * y * rlattice["a"] * rlattice["b"] * math.cos(rlattice["gamma"])
        + 2.0 * x * z * rlattice["a"] * rlattice["c"] * math.cos(rlattice["beta"])
        + 2.0 * z * y * rlattice["c"] * rlattice["b"] * math.cos(rlattice["alpha"])
    )
    return math.sqrt(s)


def scale_ei_limits(ei_limits_pg002_mev: list[float], mono_reflection: str | float) -> list[float]:
    """Port of the Ei scale factor in ``ExtractInstrumentParameters.m``.

    The facility A4Limits Ei row is defined for PG(002); for another
    monochromator reflection it is scaled by (tau_mono / tau_pg002)^2.
    """
    tau_m = get_tau(mono_reflection)
    tau_002 = get_tau("pg(002)")
    factor = (tau_m / tau_002) ** 2
    return [float(ei) * factor for ei in ei_limits_pg002_mev]


def bragg_energy_floor(reflection: str | float) -> float:
    """Lowest energy (meV) that can Bragg-scatter off the crystal.

    From ``CheckAngles.m``: ``asin(tau/(2k))`` is real only when
    ``k >= tau/2``, i.e. ``E >= 2.072*(tau/2)^2``.
    """
    tau = get_tau(reflection)
    return ENERGY_CONSTANT_MEV_ANG2 * (tau / 2.0) ** 2


def minimum_incident_energy(ei_limits_mev: list[float], mono_reflection: str | float) -> float:
    """Port of the monochromator section of ``CheckAngles.m``.

    The minimum Ei is the drum minimum unless the monochromator Bragg angle
    would be imaginary there, in which case it is the Bragg floor.
    """
    drum_min = min(ei_limits_mev)
    floor = bragg_energy_floor(mono_reflection)
    return drum_min if drum_min >= floor else floor


def analyzer_check(ef_mev: float, ana_reflection: str | float) -> dict[str, Any]:
    """Port of the analyzer section of ``CheckAngles.m``: Ef must sit above the Bragg floor."""
    floor = bragg_energy_floor(ana_reflection)
    ok = float(ef_mev) >= floor
    result: dict[str, Any] = {"ef_mev": float(ef_mev), "analyzer_bragg_floor_mev": floor, "analyzer_ok": ok}
    if not ok:
        result["analyzer_error"] = (
            f"The lattice spacing of the {ana_reflection} reflection is too small to allow "
            f"Bragg scattering off the analyzer for Ef = {ef_mev}."
        )
    return result


def energy_transfer_range(min_ei_mev: float, max_ei_mev: float, ef_mev: float) -> tuple[float, float]:
    """Port of the energy-range check in ``CheckAngles.m``: min_Ei - Ef <= E <= max_Ei - Ef."""
    return (min_ei_mev - ef_mev, max_ei_mev - ef_mev)


def _interp1(x_table: list[float], y_table: list[float], x: float) -> float:
    """MATLAB ``interp1`` (linear, NaN outside the table range) as used in the planners."""
    if len(x_table) != len(y_table) or len(x_table) < 2:
        raise ValueError("A4 limit table needs matching Ei and A4 rows with at least two entries.")
    pairs = sorted(zip(x_table, y_table), key=lambda p: p[0])
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    if x < xs[0] or x > xs[-1]:
        return float("nan")
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i + 1]:
            if xs[i + 1] == xs[i]:
                return ys[i]
            fraction = (x - xs[i]) / (xs[i + 1] - xs[i])
            return ys[i] + fraction * (ys[i + 1] - ys[i])
    return float("nan")


def q_window_at_energy(
    energy_transfer_mev: float,
    ef_mev: float,
    ei_limits_mev: list[float],
    a4_max_limits_deg: list[float],
    a4_min_deg: float,
) -> dict[str, float]:
    """Port of the Q-limit calculation in ``AccessibleQ_Plot.m``.

    ``Qmax^2 = (Ei + Ef - 2*sqrt(Ei*Ef)*cos(A4max)) / 2.072`` with A4max
    interpolated from the facility table at Ei = E + Ef, and Qmin from the
    user A4 minimum. Angles are converted degrees -> radians exactly as
    ``Hand2Num.m`` does.
    """
    ei = energy_transfer_mev + ef_mev
    a4_max_rad = _interp1(ei_limits_mev, [math.radians(a) for a in a4_max_limits_deg], ei)
    if math.isnan(a4_max_rad):
        return {"ei_mev": ei, "q_min_inv_ang": float("nan"), "q_max_inv_ang": float("nan")}
    a4_min_rad = math.radians(a4_min_deg)
    q_max_sq = (ei + ef_mev - 2.0 * math.sqrt(ei * ef_mev) * math.cos(a4_max_rad)) / ENERGY_CONSTANT_MEV_ANG2
    q_min_sq = (ei + ef_mev - 2.0 * math.sqrt(ei * ef_mev) * math.cos(a4_min_rad)) / ENERGY_CONSTANT_MEV_ANG2
    return {
        "ei_mev": ei,
        "q_min_inv_ang": math.sqrt(max(q_min_sq, 0.0)),
        "q_max_inv_ang": math.sqrt(max(q_max_sq, 0.0)),
    }


def accessible_qe_boundary(
    ef_mev: float,
    ei_limits_mev: list[float],
    a4_max_limits_deg: list[float],
    a4_min_deg: float,
    mono_reflection: str | float,
    ei_step_mev: float = DEFAULT_EI_GRID_STEP_MEV,
) -> dict[str, list[float]]:
    """Port of the accessible-region construction in ``AccessibleE_Plot.m``.

    Sweeps Ei from min_Ei to max(EiLimits) on a 0.05 meV grid, computes the
    Qmin/Qmax boundary at each E = Ei - Ef, and returns the closed boundary
    polygon ``Qall = [Qmin, reversed(Qmax)]``, ``Eall = [E, reversed(E)]``.
    """
    min_ei = minimum_incident_energy(ei_limits_mev, mono_reflection)
    max_ei = max(ei_limits_mev)
    a4_max_rad_table = [math.radians(a) for a in a4_max_limits_deg]
    a4_min_rad = math.radians(a4_min_deg)
    energies: list[float] = []
    q_min: list[float] = []
    q_max: list[float] = []
    n_steps = int(math.floor((max_ei - min_ei) / ei_step_mev + 1e-9))
    for i in range(n_steps + 1):
        ei = min_ei + i * ei_step_mev
        a4_max_rad = _interp1(ei_limits_mev, a4_max_rad_table, ei)
        if math.isnan(a4_max_rad):
            continue
        energies.append(ei - ef_mev)
        q_max_sq = (ei + ef_mev - 2.0 * math.sqrt(ei * ef_mev) * math.cos(a4_max_rad)) / ENERGY_CONSTANT_MEV_ANG2
        q_min_sq = (ei + ef_mev - 2.0 * math.sqrt(ei * ef_mev) * math.cos(a4_min_rad)) / ENERGY_CONSTANT_MEV_ANG2
        q_max.append(math.sqrt(max(q_max_sq, 0.0)))
        q_min.append(math.sqrt(max(q_min_sq, 0.0)))
    q_boundary = q_min + list(reversed(q_max))
    e_boundary = energies + list(reversed(energies))
    return {
        "energy_transfer_mev": energies,
        "q_min_inv_ang": q_min,
        "q_max_inv_ang": q_max,
        "boundary_q_inv_ang": q_boundary,
        "boundary_e_mev": e_boundary,
    }


def energy_cut_limits(q_inv_ang: float, boundary_q: list[float], boundary_e: list[float]) -> list[float]:
    """Port of the constant-Q crossing detection in ``AccessibleE_Plot.m``.

    Walks the closed boundary polygon and reports the sorted energy values
    where a vertical line at ``q_inv_ang`` crosses it. An empty list means the
    constant-Q cut is entirely outside the accessible region.
    """
    if not boundary_q:
        return []
    if q_inv_ang < min(boundary_q) or q_inv_ang > max(boundary_q):
        return []

    def _sign(value: float) -> int:
        if value > 0:
            return 1
        if value < 0:
            return -1
        return 0

    n = len(boundary_q)
    limits: list[float] = []
    for i in range(n):
        j = (i + 1) % n
        s1 = _sign(boundary_q[i] - q_inv_ang)
        s2 = _sign(boundary_q[j] - q_inv_ang)
        if s1 != s2:
            limits.append(boundary_e[i])
    return sorted(limits)


def check_accessibility(
    ef_mev: float,
    mono_reflection: str,
    ana_reflection: str,
    ei_limits_pg002_mev: list[float],
    a4_max_limits_deg: list[float],
    a4_min_deg: float,
    lattice: dict[str, float] | None = None,
    q_points_rlu: list[list[float]] | None = None,
    q_moduli_inv_ang: list[float] | None = None,
    energy_transfers_mev: list[float] | None = None,
) -> dict[str, Any]:
    """Composite accessibility check assembled from the ported ExPlanner pieces.

    Mirrors what ExPlanner does across CheckAngles / AccessibleQ_Plot /
    AccessibleE_Plot for one spectrometer configuration: validates the
    analyzer choice, reports the reachable energy-transfer window, and for
    each requested (Q, E) point reports the accessible Q window and whether
    the point falls inside it. Q points may be given as (H, K, L) in r.l.u.
    (requires ``lattice``) or directly as |Q| in inverse Angstroms.
    """
    ei_limits = scale_ei_limits(ei_limits_pg002_mev, mono_reflection)
    min_ei = minimum_incident_energy(ei_limits, mono_reflection)
    max_ei = max(ei_limits)
    analyzer = analyzer_check(ef_mev, ana_reflection)
    e_min, e_max = energy_transfer_range(min_ei, max_ei, ef_mev)

    rlattice = reciprocal_lattice(lattice) if lattice else None
    targets: list[dict[str, Any]] = []
    for index, q_mod in enumerate(q_moduli_inv_ang or []):
        targets.append({"label": f"|Q|[{index}]", "q_inv_ang": float(q_mod)})
    for index, hkl in enumerate(q_points_rlu or []):
        if rlattice is None:
            raise ValueError("q_points_rlu requires lattice parameters (a, b, c, alpha, beta, gamma).")
        h, k, l = (float(v) for v in hkl)
        targets.append({"label": f"({h}, {k}, {l})", "hkl": [h, k, l], "q_inv_ang": modvec(h, k, l, rlattice)})

    boundary = accessible_qe_boundary(ef_mev, ei_limits, a4_max_limits_deg, a4_min_deg, mono_reflection)

    point_results: list[dict[str, Any]] = []
    for target in targets:
        per_energy: list[dict[str, Any]] = []
        for energy in energy_transfers_mev or [0.0]:
            in_energy_window = e_min <= energy <= e_max
            window = q_window_at_energy(energy, ef_mev, ei_limits, a4_max_limits_deg, a4_min_deg)
            q_ok = (
                in_energy_window
                and not math.isnan(window["q_max_inv_ang"])
                and window["q_min_inv_ang"] <= target["q_inv_ang"] <= window["q_max_inv_ang"]
            )
            per_energy.append(
                {
                    "energy_transfer_mev": float(energy),
                    "within_energy_window": in_energy_window,
                    "q_window_inv_ang": [window["q_min_inv_ang"], window["q_max_inv_ang"]],
                    "accessible": bool(q_ok and analyzer["analyzer_ok"]),
                }
            )
        cut_limits = energy_cut_limits(target["q_inv_ang"], boundary["boundary_q_inv_ang"], boundary["boundary_e_mev"])
        point_results.append(
            {
                **target,
                "energy_checks": per_energy,
                "constant_q_energy_cut_limits_mev": cut_limits,
            }
        )

    return {
        "ef_mev": float(ef_mev),
        "monochromator": str(mono_reflection),
        "analyzer": str(ana_reflection),
        "ei_limits_mev": ei_limits,
        "minimum_incident_energy_mev": min_ei,
        "energy_transfer_window_mev": [e_min, e_max],
        "a4_min_deg": float(a4_min_deg),
        "a4_max_limits_deg": [float(a) for a in a4_max_limits_deg],
        "analyzer_check": analyzer,
        "points": point_results,
        "parity_status": PARITY_STATUS,
        "source_files": [
            "ExPlanner9/PlannerFunctions/CheckAngles.m",
            "ExPlanner9/PlannerFunctions/AccessibleQ_Plot.m",
            "ExPlanner9/PlannerFunctions/AccessibleE_Plot.m",
            "ExPlanner9/PlannerFunctions/Hand2Num.m",
            "ExPlanner9/PlannerFunctions/ExtractInstrumentParameters.m",
            "ExPlanner9/ResLib3.4c/GetTau.m",
            "ExPlanner9/ResLib3.4c/star.m",
            "ExPlanner9/ResLib3.4c/scalar.m",
        ],
        "safety_note": "Planning/simulation only; not approved instrument operation.",
    }
