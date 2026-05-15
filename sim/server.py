"""Async Modbus TCP slave that simulates a 3-phase energy meter.

Register map (slave_id from config, holding registers, byte order ABCD):

  HR  0..1   FLOAT32  voltage_l1            V
  HR  2..3   FLOAT32  voltage_l2            V
  HR  4..5   FLOAT32  voltage_l3            V
  HR  6..7   FLOAT32  current_l1            A
  HR  8..9   FLOAT32  current_l2            A
  HR 10..11  FLOAT32  current_l3            A
  HR 12..13  FLOAT32  power_active_total    W
  HR 14..15  FLOAT32  power_reactive_total  var
  HR 16..17  FLOAT32  power_apparent_total  VA
  HR 18..19  FLOAT32  power_factor          -
  HR 20..21  FLOAT32  frequency             Hz
  HR 30..31  UINT32   energy_active_import  Wh   (monotonic)
  HR 32..33  UINT32   energy_active_export  Wh   (monotonic, slower)
  HR 100     UINT16   status                bitfield
"""

import asyncio
import logging
import math
import os
import random
import time
from pathlib import Path

import yaml
from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusServerContext,
    ModbusSlaveContext,
)
from pymodbus.server import StartAsyncTcpServer

from .registers import float32_to_regs, u32_to_regs

LOG = logging.getLogger("modbus_sim")

CONFIG_PATH = Path(os.environ.get("SIM_CONFIG", Path(__file__).parent / "config.yaml"))

HR_SIZE = 200  # registers 0..199; ample headroom for the layout


def load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_context(slave_id: int) -> ModbusServerContext:
    block = ModbusSequentialDataBlock(0, [0] * HR_SIZE)
    slave = ModbusSlaveContext(hr=block, zero_mode=True)
    return ModbusServerContext(slaves={slave_id: slave}, single=False)


def _set_float32(slave: ModbusSlaveContext, addr: int, value: float) -> None:
    hi, lo = float32_to_regs(value)
    slave.setValues(3, addr, [hi, lo])  # fc=3 → holding registers


def _set_u32(slave: ModbusSlaveContext, addr: int, value: int) -> None:
    hi, lo = u32_to_regs(value)
    slave.setValues(3, addr, [hi, lo])


def _set_u16(slave: ModbusSlaveContext, addr: int, value: int) -> None:
    slave.setValues(3, addr, [int(value) & 0xFFFF])


class EnergyMeterModel:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.t0 = time.monotonic()
        self.last_tick = self.t0
        self.currents = [cfg["nominal_current"]] * 3
        self.energy_import_wh = 0.0
        self.energy_export_wh = 0.0

    def step(self) -> dict:
        now = time.monotonic()
        dt = max(0.0, now - self.last_tick)
        self.last_tick = now
        t = now - self.t0

        v_nom = self.cfg["nominal_voltage"]
        v_noise = self.cfg["voltage_noise"]
        voltages = [
            v_nom + v_noise * math.sin(t + phase)
            for phase in (0.0, 2 * math.pi / 3, 4 * math.pi / 3)
        ]

        step = self.cfg["current_walk_step"]
        i_min = self.cfg["current_min"]
        i_max = self.cfg["current_max"]
        self.currents = [
            min(i_max, max(i_min, i + random.uniform(-step, step)))
            for i in self.currents
        ]

        pf = max(
            0.0,
            min(
                1.0,
                self.cfg["nominal_power_factor"]
                + random.uniform(-self.cfg["pf_noise"], self.cfg["pf_noise"]),
            ),
        )
        freq = self.cfg["nominal_frequency"] + random.uniform(
            -self.cfg["frequency_noise"], self.cfg["frequency_noise"]
        )

        p_active = sum(v * i for v, i in zip(voltages, self.currents)) * pf
        # sin(acos(pf)) without numeric drift for pf in [0,1]
        sin_phi = math.sqrt(max(0.0, 1.0 - pf * pf))
        p_reactive = sum(v * i for v, i in zip(voltages, self.currents)) * sin_phi
        p_apparent = math.sqrt(p_active * p_active + p_reactive * p_reactive)

        speedup = self.cfg.get("energy_speedup", 1.0)
        self.energy_import_wh += (p_active / 3600.0) * dt * speedup
        self.energy_export_wh += (p_active / 3600.0) * dt * speedup * 0.1

        # alarm bit toggles every 60s; online bit always set
        alarm_on = int((t // 60) % 2) == 1
        status = 0b01 | (0b10 if alarm_on else 0)

        return {
            "voltages": voltages,
            "currents": list(self.currents),
            "p_active": p_active,
            "p_reactive": p_reactive,
            "p_apparent": p_apparent,
            "pf": pf,
            "freq": freq,
            "energy_import_wh": int(self.energy_import_wh),
            "energy_export_wh": int(self.energy_export_wh),
            "status": status,
        }


def apply_to_slave(slave: ModbusSlaveContext, snap: dict) -> None:
    for i, v in enumerate(snap["voltages"]):
        _set_float32(slave, i * 2, v)
    for i, c in enumerate(snap["currents"]):
        _set_float32(slave, 6 + i * 2, c)
    _set_float32(slave, 12, snap["p_active"])
    _set_float32(slave, 14, snap["p_reactive"])
    _set_float32(slave, 16, snap["p_apparent"])
    _set_float32(slave, 18, snap["pf"])
    _set_float32(slave, 20, snap["freq"])
    _set_u32(slave, 30, snap["energy_import_wh"])
    _set_u32(slave, 32, snap["energy_export_wh"])
    _set_u16(slave, 100, snap["status"])


async def updater(
    context: ModbusServerContext, slave_id: int, model: EnergyMeterModel, tick: float
) -> None:
    slave = context[slave_id]
    while True:
        snap = model.step()
        apply_to_slave(slave, snap)
        LOG.debug(
            "tick V1=%.2f I1=%.2f P=%.1fW E_imp=%dWh status=%d",
            snap["voltages"][0],
            snap["currents"][0],
            snap["p_active"],
            snap["energy_import_wh"],
            snap["status"],
        )
        await asyncio.sleep(tick)


async def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    cfg = load_config()
    slave_id = int(cfg["slave_id"])
    context = build_context(slave_id)
    model = EnergyMeterModel(cfg)
    # Seed the registers immediately so the first read after connect is meaningful.
    apply_to_slave(context[slave_id], model.step())

    asyncio.create_task(updater(context, slave_id, model, float(cfg["tick_seconds"])))

    addr = (cfg["host"], int(cfg["port"]))
    LOG.info("Modbus TCP slave listening on %s:%d (slave id %d)", *addr, slave_id)
    await StartAsyncTcpServer(context=context, address=addr)


if __name__ == "__main__":
    asyncio.run(main())
