"""Unit tests for the meter physics (pytest, no network)."""

import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402

from sim.model import EnergyMeterModel  # noqa: E402
from sim.points import POINTS, REGISTER_WIDTH  # noqa: E402

CFG = yaml.safe_load((Path(__file__).resolve().parent.parent / "sim" / "config.yaml").read_text())


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def run(cfg=None, seconds=60, tick=1.0):
    clock = Clock()
    m = EnergyMeterModel(dict(cfg or CFG), clock=clock, rng=random.Random(1))
    snaps = []
    for _ in range(int(seconds / tick)):
        clock.t += tick
        snaps.append(m.step())
    return snaps


def test_every_point_has_a_value():
    snap = run(seconds=2)[-1]
    assert {p.name for p in POINTS} <= set(snap)


def test_modbus_registers_do_not_overlap_and_legacy_addresses_kept():
    used = {}
    for p in POINTS:
        for r in range(p.modbus_addr, p.modbus_addr + REGISTER_WIDTH[p.modbus_type]):
            assert r not in used, f"{p.name} overlaps {used[r]} at {r}"
            used[r] = p.name
    legacy = {"voltage_l1": 0, "current_l1": 6, "power_active_total": 12, "power_factor": 18,
              "frequency": 20, "energy_active_import": 30, "energy_active_export": 32, "status": 100}
    addr = {p.name: p.modbus_addr for p in POINTS}
    assert all(addr[k] == v for k, v in legacy.items())


def test_opcua_ids_and_names_unique():
    assert len({p.opcua_id for p in POINTS}) == len(POINTS)
    assert len({p.opcua_name for p in POINTS}) == len(POINTS)


def test_phase_sums_and_power_triangle():
    for s in run(seconds=30):
        assert math.isclose(s["power_active_total"], sum(s[f"power_active_l{n}"] for n in (1, 2, 3)), rel_tol=1e-9)
        assert math.isclose(s["power_reactive_total"], sum(s[f"power_reactive_l{n}"] for n in (1, 2, 3)), rel_tol=1e-9)
        for n in (1, 2, 3):
            p, q, sa = s[f"power_active_l{n}"], s[f"power_reactive_l{n}"], s[f"power_apparent_l{n}"]
            assert math.isclose(sa, math.hypot(p, q), rel_tol=1e-9)
            assert math.isclose(s[f"power_factor_l{n}"], p / sa, rel_tol=1e-9)
            assert math.isclose(sa, s[f"voltage_l{n}"] * s[f"current_l{n}"], rel_tol=1e-9)


def test_line_voltage_is_root3_of_phase_voltage():
    s = run(seconds=5)[-1]
    for key in ("voltage_l1_l2", "voltage_l2_l3", "voltage_l3_l1"):
        assert 390 < s[key] < 408


def test_counters_monotonic_and_integrate_power():
    snaps = run(seconds=3600)
    for key in ("energy_active_import", "energy_active_export", "energy_reactive_import", "energy_apparent"):
        values = [s[key] for s in snaps]
        assert values == sorted(values)
    mean_p = sum(s["power_active_total"] for s in snaps) / len(snaps)
    assert abs(snaps[-1]["energy_active_import"] - mean_p) <= mean_p * 0.01 + 1  # 1 h of mean P in Wh


def test_demand_is_window_average():
    snaps = run(seconds=1800)
    mean_last_15 = sum(s["power_active_total"] for s in snaps[-900:]) / 900
    assert math.isclose(snaps[-1]["power_active_demand"], mean_last_15, rel_tol=0.01)
    assert snaps[-1]["power_active_demand_max"] >= snaps[-1]["power_active_demand"]


def test_machine_profile_has_idle_phases():
    cfg = dict(CFG, load_profile="machine", production_min_seconds=120, production_max_seconds=120,
               idle_min_seconds=120, idle_max_seconds=120)
    p = [s["power_active_total"] for s in run(cfg, seconds=1200)]
    assert min(p) < 0.5 * max(p)


def test_neutral_current_small_when_balanced():
    s = run(seconds=5)[-1]
    assert s["current_n"] < 0.5 * s["current_l1"]
