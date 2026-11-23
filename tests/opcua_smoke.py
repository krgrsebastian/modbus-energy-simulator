"""OPC UA client smoke test: reads every node in sim/points.py by its NodeId.

Usage:
    python tests/opcua_smoke.py                          # opc.tcp://127.0.0.1:4840
    python tests/opcua_smoke.py --url opc.tcp://host:4840
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from asyncua import Client  # noqa: E402

from sim.opcua_server import NAMESPACE_URI  # noqa: E402
from sim.points import POINTS  # noqa: E402


async def main(url: str, interval: float) -> int:
    async with Client(url) as client:
        ns = await client.get_namespace_index(NAMESPACE_URI)
        if ns != 2:
            print(f"FAIL: namespace index {ns}, expected 2", file=sys.stderr)
            return 2
        first = {}
        for p in POINTS:
            node = client.get_node(p.node_id)
            name = (await node.read_browse_name()).Name
            if name != p.opcua_name:
                print(f"FAIL: {p.node_id} is {name}, expected {p.opcua_name}", file=sys.stderr)
                return 2
            first[p.name] = await node.read_value()
            print(f"  {p.node_id:<14} {name:<10} = {first[p.name]:.3f}")
        await asyncio.sleep(interval)
        later = await client.get_node(POINTS[0].node_id).read_value()
        energy = await client.get_node(next(p for p in POINTS if p.name == "energy_active_import").node_id).read_value()
        if energy < first["energy_active_import"]:
            print("FAIL: energy counter went backwards", file=sys.stderr)
            return 2
        if later == first[POINTS[0].name]:
            print("FAIL: values do not update", file=sys.stderr)
            return 2
    print("OK")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="opc.tcp://127.0.0.1:4840")
    ap.add_argument("--interval", type=float, default=2.5)
    a = ap.parse_args()
    raise SystemExit(asyncio.run(main(a.url, a.interval)))
