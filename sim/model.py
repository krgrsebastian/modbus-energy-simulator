"""Protocol-free 3-phase energy meter: config loading and the physics.

Both servers (Modbus in sim.server, OPC UA in sim.opcua_server) call
EnergyMeterModel.step() once per tick and publish the flat snapshot it returns.
Snapshot keys are the point names in sim.points.
"""

import cmath
import logging
import math
import os
import random
import time
from collections import deque
from pathlib import Path

import yaml

LOG = logging.getLogger("energy_sim")

CONFIG_PATH = Path(os.environ.get("SIM_CONFIG", Path(__file__).parent / "config.yaml"))

# Phase angles of L1, L2, L3 (rotating field L1 -> L2 -> L3).
PHASE_ANGLES = (0.0, -2 * math.pi / 3, 2 * math.pi / 3)


def load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return apply_env_overrides(cfg)


def apply_env_overrides(cfg: dict) -> dict:
    """Let any scalar in config.yaml be overridden by SIM_<KEY>.

    One rule instead of a hand-maintained list of supported variables. The value
    is coerced to the type already in the config, and a value that will not
    convert is reported rather than silently ignored: a typo in a compose file
    should not look like it worked.
    """
    for key, current in list(cfg.items()):
        raw = os.environ.get("SIM_" + key.upper())
        if raw is None:
            continue
        try:
            cfg[key] = type(current)(raw)
        except (TypeError, ValueError):
            LOG.warning(
                "ignoring SIM_%s=%r: cannot read it as %s (keeping %r)",
                key.upper(), raw, type(current).__name__, current,
            )
            continue
        LOG.info("config override: %s = %r (was %r)", key, cfg[key], current)
    return cfg


def check_config(cfg: dict) -> None:
    if not cfg["current_min"] <= cfg["nominal_current"] <= cfg["current_max"]:
        LOG.warning(
            "nominal_current %.2f A is outside [%.2f, %.2f]: the walk is clamped to the "
            "band, so the meter will not draw what you asked for. Raise SIM_CURRENT_MAX "
            "(or lower SIM_CURRENT_MIN) to match.",
            cfg["nominal_current"], cfg["current_min"], cfg["current_max"],
        )
    if cfg.get("load_profile", "constant") not in ("constant", "machine"):
        LOG.warning("unknown load_profile %r, using 'constant'", cfg["load_profile"])


def _clamp(x: float, lo: float, hi: float) -> float:
    return min(hi, max(lo, x))


class EnergyMeterModel:
    def __init__(self, cfg: dict, clock=time.monotonic, rng: random.Random | None = None) -> None:
        self.cfg = cfg
        self.clock = clock
        self.rng = rng or random.Random()
        self.t0 = clock()
        self.last_tick = self.t0
        self.currents = [cfg["nominal_current"]] * 3
        self.thd_i = [cfg.get("thd_current_nominal", 8.0)] * 3
        self.energy = {"active_import": 0.0, "active_export": 0.0, "reactive_import": 0.0, "apparent": 0.0}
        self.demand_samples: deque[tuple[float, float, float]] = deque()  # (t, dt, P)
        self.demand_max = 0.0
        # machine load profile: alternate production and idle
        self.producing = True
        self.state_until = self.t0 + self._state_duration()

    # --- load profile -------------------------------------------------------

    def _state_duration(self) -> float:
        c = self.cfg
        if self.producing:
            return self.rng.uniform(c.get("production_min_seconds", 300), c.get("production_max_seconds", 900))
        return self.rng.uniform(c.get("idle_min_seconds", 60), c.get("idle_max_seconds", 240))

    def _target_current(self, now: float) -> float:
        i_nom = self.cfg["nominal_current"]
        if self.cfg.get("load_profile", "constant") != "machine":
            return i_nom
        if now >= self.state_until:
            self.producing = not self.producing
            self.state_until = now + self._state_duration()
        return i_nom if self.producing else i_nom * self.cfg.get("idle_load_factor", 0.25)

    # --- one tick -------------------------------------------------------------

    def step(self) -> dict:
        c = self.cfg
        now = self.clock()
        dt = max(0.0, now - self.last_tick)
        self.last_tick = now
        t = now - self.t0
        rnd = self.rng.uniform

        # Phase voltages: slow sine around nominal, shifted per phase.
        v_mag = [
            c["nominal_voltage"] + c["voltage_noise"] * math.sin(t + k * 2 * math.pi / 3)
            for k in range(3)
        ]

        # Currents: bounded random walk pulled toward the target. Without the pull
        # the walk forgets nominal_current within hours and two differently sized
        # meters become indistinguishable.
        target = self._target_current(now)
        step, pull = c["current_walk_step"], c.get("current_pull", 0.02)
        self.currents = [
            _clamp(i + rnd(-step, step) + pull * (target - i), c["current_min"], c["current_max"])
            for i in self.currents
        ]

        pf = [_clamp(c["nominal_power_factor"] + rnd(-c["pf_noise"], c["pf_noise"]), 0.0, 1.0) for _ in range(3)]
        phi = [math.acos(x) for x in pf]

        s_ph = [v * i for v, i in zip(v_mag, self.currents)]
        p_ph = [s * x for s, x in zip(s_ph, pf)]
        q_ph = [s * math.sin(f) for s, f in zip(s_ph, phi)]
        p_tot, q_tot = sum(p_ph), sum(q_ph)
        s_tot = math.hypot(p_tot, q_tot)

        # Phasors for line voltages and the neutral current (current lags voltage by phi).
        v_vec = [cmath.rect(v, a) for v, a in zip(v_mag, PHASE_ANGLES)]
        i_vec = [cmath.rect(i, a - f) for i, a, f in zip(self.currents, PHASE_ANGLES, phi)]
        v_ll = [abs(v_vec[0] - v_vec[1]), abs(v_vec[1] - v_vec[2]), abs(v_vec[2] - v_vec[0])]
        i_n = abs(sum(i_vec))

        # Harmonics: voltage THD jitters around nominal, current THD walks slowly.
        thd_u = [max(0.0, c.get("thd_voltage_nominal", 2.0) + rnd(-0.3, 0.3)) for _ in range(3)]
        thd_i_nom = c.get("thd_current_nominal", 8.0)
        self.thd_i = [_clamp(x + rnd(-0.3, 0.3) + 0.05 * (thd_i_nom - x), 0.0, 100.0) for x in self.thd_i]

        freq = c["nominal_frequency"] + rnd(-c["frequency_noise"], c["frequency_noise"])

        # Counters integrate real elapsed time (times energy_speedup for demos).
        k = dt * c.get("energy_speedup", 1.0) / 3600.0
        self.energy["active_import"] += p_tot * k
        self.energy["active_export"] += p_tot * k * 0.1
        self.energy["reactive_import"] += q_tot * k
        self.energy["apparent"] += s_tot * k

        # Demand: time-weighted average of P over the sliding window.
        window = c.get("demand_window_seconds", 900)
        self.demand_samples.append((now, dt, p_tot))
        while self.demand_samples and self.demand_samples[0][0] < now - window:
            self.demand_samples.popleft()
        weight = sum(d for _, d, _ in self.demand_samples)
        demand = sum(d * p for _, d, p in self.demand_samples) / weight if weight > 0 else p_tot
        self.demand_max = max(self.demand_max, demand)

        alarm_on = int((t // 60) % 2) == 1
        status = 0b01 | (0b10 if alarm_on else 0)

        snap = {
            "frequency": freq,
            "power_active_total": p_tot,
            "power_reactive_total": q_tot,
            "power_apparent_total": s_tot,
            "power_factor": p_tot / s_tot if s_tot > 0 else 1.0,
            "current_n": i_n,
            "power_active_demand": demand,
            "power_active_demand_max": self.demand_max,
            "energy_active_import": int(self.energy["active_import"]),
            "energy_active_export": int(self.energy["active_export"]),
            "energy_reactive_import": int(self.energy["reactive_import"]),
            "energy_apparent": int(self.energy["apparent"]),
            "status": status,
        }
        for n in range(3):
            ph = f"l{n + 1}"
            snap[f"voltage_{ph}"] = v_mag[n]
            snap[f"current_{ph}"] = self.currents[n]
            snap[f"power_active_{ph}"] = p_ph[n]
            snap[f"power_reactive_{ph}"] = q_ph[n]
            snap[f"power_apparent_{ph}"] = s_ph[n]
            snap[f"power_factor_{ph}"] = pf[n]
            snap[f"thd_voltage_{ph}"] = thd_u[n]
            snap[f"thd_current_{ph}"] = self.thd_i[n]
        snap["voltage_l1_l2"], snap["voltage_l2_l3"], snap["voltage_l3_l1"] = v_ll
        return snap
