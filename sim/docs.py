"""Print the data point tables (Markdown) from sim/points.py.

    python -m sim.docs            # both tables
    python -m sim.docs modbus     # Modbus register map only
    python -m sim.docs opcua      # OPC UA node list only
"""

import sys

from .points import POINTS


def modbus_table() -> str:
    rows = ["| Address | Type | Tag | Unit | Description |", "|--|--|--|--|--|"]
    for p in sorted(POINTS, key=lambda p: p.modbus_addr):
        rows.append(f"| {p.modbus_addr} | {p.modbus_type} | {p.name} | {p.unit} | {p.description} |")
    return "\n".join(rows)


def opcua_table() -> str:
    rows = ["| NodeId | Browse name | Data type | Unit | Description |", "|--|--|--|--|--|"]
    for p in sorted(POINTS, key=lambda p: p.opcua_id):
        dtype = "UInt16" if p.modbus_type == "UINT16" else "Double"
        rows.append(f"| `{p.node_id}` | {p.opcua_name} | {dtype} | {p.unit} | {p.description} |")
    return "\n".join(rows)


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "modbus"):
        print(modbus_table())
    if which == "all":
        print()
    if which in ("all", "opcua"):
        print(opcua_table())
