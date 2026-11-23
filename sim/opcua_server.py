"""OPC UA server for the simulated 3-phase energy meter (same model as the Modbus server).

Address space (namespace index 2, URI below), flat and numeric on purpose:

  Objects/EM_01 (ns=2;i=5000)/<code>   ns=2;i=<id>   e.g. P_SUM = ns=2;i=6100

No descriptions: the meaning of each node is only in the vendor documentation.

Security: None, anonymous login. The endpoint has no path, because benthos-umh
appends the path it discovers to the one configured and a doubled path fails.
The server listens on all interfaces and answers GetEndpoints with the host the
client dialled, so `opc.tcp://<service-name>:4840` works from another container.
"""

import asyncio
import logging
import os

from asyncua import Server, ua

from .model import EnergyMeterModel, check_config, load_config
from .points import POINTS

LOG = logging.getLogger("opcua_sim")

NAMESPACE_URI = "urn:umh:energy-meter-simulator"


def variant(point_type: str, value) -> ua.Variant:
    if point_type == "UINT16":
        return ua.Variant(int(value), ua.VariantType.UInt16)
    return ua.Variant(float(value), ua.VariantType.Double)


async def build_server(cfg: dict) -> tuple[Server, dict]:
    server = Server()
    await server.init()
    port = int(cfg.get("opcua_port", 4840))
    server.set_endpoint(f"opc.tcp://0.0.0.0:{port}")
    server.set_server_name("UMH Energy Meter Simulator")
    server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
    server.set_identity_tokens([ua.AnonymousIdentityToken])
    idx = await server.register_namespace(NAMESPACE_URI)
    if idx != 2:
        LOG.warning("namespace index is %d, not 2: NodeIds in the docs will not match", idx)

    meter = await server.nodes.objects.add_object(ua.NodeId(5000, idx), ua.QualifiedName("EM_01", idx))
    nodes: dict[str, object] = {}
    for p in POINTS:
        nodes[p.name] = await meter.add_variable(
            ua.NodeId(p.opcua_id, idx), ua.QualifiedName(p.opcua_name, idx), variant(p.modbus_type, 0)
        )
    return server, nodes


async def publish(nodes: dict, snap: dict) -> None:
    for p in POINTS:
        await nodes[p.name].write_value(variant(p.modbus_type, snap[p.name]))


async def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # asyncua logs every subscription and session at INFO
    logging.getLogger("asyncua").setLevel(logging.WARNING)
    cfg = load_config()
    check_config(cfg)
    model = EnergyMeterModel(cfg)
    server, nodes = await build_server(cfg)
    await publish(nodes, model.step())
    tick = float(cfg["tick_seconds"])
    async with server:
        LOG.info("OPC UA server listening on port %d (%d points, ns=2)", int(cfg.get("opcua_port", 4840)), len(POINTS))
        while True:
            await asyncio.sleep(tick)
            await publish(nodes, model.step())


if __name__ == "__main__":
    asyncio.run(main())
