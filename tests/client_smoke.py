"""Standalone pymodbus client smoke test.

Reads the full register map and prints decoded values. No benthos needed.

Usage:
    python tests/client_smoke.py                       # connects to 127.0.0.1:1502
    python tests/client_smoke.py --host x --port 1502
"""

import argparse
import sys
import time
from pathlib import Path

# Allow `python tests/client_smoke.py` from repo root without install.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pymodbus.client import ModbusTcpClient  # noqa: E402

from sim.registers import regs_to_float32, regs_to_u32  # noqa: E402

from sim.points import POINTS  # noqa: E402

LAYOUT = [(p.name, p.modbus_addr, p.modbus_type.lower()) for p in POINTS]


def read_once(client: ModbusTcpClient, slave: int) -> dict[str, float | int]:
    out: dict[str, float | int] = {}
    for name, addr, kind in LAYOUT:
        count = 1 if kind == "uint16" else 2
        rr = client.read_holding_registers(address=addr, count=count, slave=slave)
        if rr.isError():
            raise RuntimeError(f"read {name}@{addr} failed: {rr}")
        regs = rr.registers
        if kind == "float32":
            out[name] = regs_to_float32(regs[0], regs[1])
        elif kind == "uint32":
            out[name] = regs_to_u32(regs[0], regs[1])
        else:
            out[name] = regs[0]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=1502)
    ap.add_argument("--slave", type=int, default=1)
    ap.add_argument("--iterations", type=int, default=2)
    ap.add_argument("--interval", type=float, default=2.0)
    args = ap.parse_args()

    client = ModbusTcpClient(host=args.host, port=args.port, timeout=3)
    if not client.connect():
        print(f"could not connect to {args.host}:{args.port}", file=sys.stderr)
        return 1

    try:
        last_energy: int | None = None
        for i in range(args.iterations):
            snap = read_once(client, args.slave)
            print(f"--- iteration {i + 1} ---")
            for k, v in snap.items():
                if isinstance(v, float):
                    print(f"  {k:<24} = {v:.3f}")
                else:
                    print(f"  {k:<24} = {v}")

            energy = int(snap["energy_active_import"])
            if last_energy is not None and energy < last_energy:
                print(f"FAIL: energy counter went backwards: {last_energy} -> {energy}", file=sys.stderr)
                return 2
            last_energy = energy

            if i + 1 < args.iterations:
                time.sleep(args.interval)
        print("OK")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
