"""Modbus TCP slave for the simulated 3-phase energy meter.

Holding registers (FC 0x03), byte order ABCD. The register map is sim/points.py;
run `python -m sim.docs` to print it.
"""

import asyncio
import logging
import os

from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusServerContext,
    ModbusSlaveContext,
)
from pymodbus.server import StartAsyncTcpServer

from .model import EnergyMeterModel, check_config, load_config
from .points import POINTS
from .registers import float32_to_regs, u32_to_regs

LOG = logging.getLogger("modbus_sim")

HR_SIZE = 200  # registers 0..199; ample headroom for the layout


def build_context(slave_id: int) -> ModbusServerContext:
    block = ModbusSequentialDataBlock(0, [0] * HR_SIZE)
    # 3.8 dropped the zero_mode kwarg; the datastore is zero-based either way,
    # so register 0 in the map is still holding register 0 on the wire.
    slave = ModbusSlaveContext(hr=block)
    return ModbusServerContext(slaves={slave_id: slave}, single=False)


def encode(point_type: str, value) -> list[int]:
    if point_type == "FLOAT32":
        return list(float32_to_regs(value))
    if point_type == "UINT32":
        return list(u32_to_regs(value))
    return [int(value) & 0xFFFF]


def apply_to_slave(slave: ModbusSlaveContext, snap: dict) -> None:
    for p in POINTS:
        slave.setValues(3, p.modbus_addr, encode(p.modbus_type, snap[p.name]))  # fc=3: holding


async def updater(context: ModbusServerContext, slave_id: int, model: EnergyMeterModel, tick: float) -> None:
    slave = context[slave_id]
    while True:
        snap = model.step()
        apply_to_slave(slave, snap)
        LOG.debug(
            "tick V1=%.2f I1=%.2f P=%.1fW E_imp=%dWh status=%d",
            snap["voltage_l1"], snap["current_l1"], snap["power_active_total"],
            snap["energy_active_import"], snap["status"],
        )
        await asyncio.sleep(tick)


async def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    cfg = load_config()
    check_config(cfg)
    slave_id = int(cfg["slave_id"])
    context = build_context(slave_id)
    model = EnergyMeterModel(cfg)
    # Seed the registers immediately so the first read after connect is meaningful.
    apply_to_slave(context[slave_id], model.step())

    asyncio.create_task(updater(context, slave_id, model, float(cfg["tick_seconds"])))

    addr = (cfg["host"], int(cfg["port"]))
    LOG.info("Modbus TCP slave listening on %s:%d (slave id %d, %d points)", *addr, slave_id, len(POINTS))
    await StartAsyncTcpServer(context=context, address=addr)


if __name__ == "__main__":
    asyncio.run(main())
