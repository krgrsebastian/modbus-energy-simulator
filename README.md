# Modbus Energy Simulator

A small Docker container that simulates a 3-phase energy meter over Modbus TCP.
Use it during benthos-umh / UMH development when you don't have a real meter
on the bench.

The compose file brings up the simulator side-by-side with
`benthos-umh:latest` configured as a Modbus client. Within a few seconds you
should see decoded JSON messages stream to stdout.

## Quick start

```bash
docker compose up --build
```

The simulator listens on `tcp://localhost:1502` (also reachable from
`benthos-umh` over the compose network as `modbus-simulator:1502`).

Tear down with `docker compose down`.

## Register map

Slave ID `1`, all values in **holding registers** (function code `0x03`), byte
order `ABCD` (big-endian). FLOAT32 / UINT32 spans two consecutive registers.

| Address | Type    | Tag                    | Unit | Behavior                                         |
|---------|---------|------------------------|------|--------------------------------------------------|
| 0       | FLOAT32 | voltage_l1             | V    | 230 + 2·sin(t)                                   |
| 2       | FLOAT32 | voltage_l2             | V    | 230 + 2·sin(t + 2π/3)                            |
| 4       | FLOAT32 | voltage_l3             | V    | 230 + 2·sin(t + 4π/3)                            |
| 6       | FLOAT32 | current_l1             | A    | 5 A + bounded random walk                        |
| 8       | FLOAT32 | current_l2             | A    | 5 A + bounded random walk                        |
| 10      | FLOAT32 | current_l3             | A    | 5 A + bounded random walk                        |
| 12      | FLOAT32 | power_active_total     | W    | Σ V·I·PF                                         |
| 14      | FLOAT32 | power_reactive_total   | var  | Σ V·I·sin φ                                      |
| 16      | FLOAT32 | power_apparent_total   | VA   | √(P² + Q²)                                       |
| 18      | FLOAT32 | power_factor           | —    | 0.92 ± 0.02                                      |
| 20      | FLOAT32 | frequency              | Hz   | 50.0 ± 0.05                                      |
| 30      | UINT32  | energy_active_import   | Wh   | monotonic, += P·Δt                               |
| 32      | UINT32  | energy_active_export   | Wh   | monotonic, slower                                |
| 100     | UINT16  | status                 | bits | b0 = online (always 1), b1 = alarm (toggles 60s) |

## Connecting from your own client

The included `benthos/modbus.yaml` is the simplest example. Any Modbus TCP
client works — point it at `127.0.0.1:1502`, slave ID 1, big-endian word
order.

Standalone smoke test (Python, no Docker required for the client):

```bash
pip install pymodbus==3.7.* pyyaml
python tests/client_smoke.py --host 127.0.0.1 --port 1502
```

Pass criteria:

- `voltage_l1` ∈ [228, 232]
- `current_l1` ∈ [0.5, 20]
- `frequency` ∈ [49.9, 50.1]
- `energy_active_import` strictly increases between iterations
- `status` is 1 or 3 (alarm bit toggles every 60s)

## Tuning

Edit `sim/config.yaml` and rebuild. The container reads the file at startup:

```yaml
port: 1502
slave_id: 1
tick_seconds: 1.0
nominal_voltage: 230.0
nominal_current: 5.0
nominal_power_factor: 0.92
nominal_frequency: 50.0
voltage_noise: 2.0
current_walk_step: 0.2
...
```

To run the simulator outside Docker:

```bash
pip install pymodbus==3.7.* pyyaml
python -m sim.server
```
