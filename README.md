# Modbus Energy Simulator

[![Docker Pulls](https://img.shields.io/docker/pulls/skumh/modbus-energy-simulator)](https://hub.docker.com/r/skumh/modbus-energy-simulator)
[![Docker Image Version](https://img.shields.io/docker/v/skumh/modbus-energy-simulator?sort=semver)](https://hub.docker.com/r/skumh/modbus-energy-simulator/tags)

A small Docker container that simulates a 3-phase energy meter over Modbus TCP.
Use it during benthos-umh / UMH development when you don't have a real meter
on the bench.

Published image (multi-arch, `linux/amd64` + `linux/arm64`):

```
docker pull skumh/modbus-energy-simulator:0.2.0
```

## Quick start — just the simulator

```bash
docker run --rm -p 1502:1502 skumh/modbus-energy-simulator:0.2.0
```

The simulator listens on `tcp://localhost:1502`. Point any Modbus TCP client
at it (slave ID 1, big-endian word order).

## Quick start — with benthos-umh + UMH Core

The included `docker-compose.yml` brings up the simulator side-by-side with
benthos-umh / UMH Core (`umh-core`). Within a few seconds you should see
decoded JSON messages flowing through the bridge.

```bash
docker compose up
```

Replace `AUTH_TOKEN` in `docker-compose.yml` with your own UMH Core token
before starting (`docker compose down` to tear down).

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

## Give it a log limit

The container inherits the daemon's logging defaults unless you say otherwise,
and an unbounded json-file log turns any log loop into a disk-full outage. In
compose:

```yaml
    logging:
      driver: json-file
      options: { max-size: "10m", max-file: "3" }
```

This is not hypothetical here. Up to 0.1.0 the server leaked one *listening*
socket per closed connection (a pymodbus 3.7 bug), so a client that reconnects
walked the process up to the 1024 file-descriptor limit. From that point every
connection attempt failed to bind and pymodbus logged it — measured at 37,000
lines a second, 4.3 MB/s, about 15 GB an hour — which pegged a core in log
formatting and dragged `dockerd` down with it. 0.1.1 pins pymodbus 3.8, which
does not leak: 1800 connect/close cycles leave the process at 9 descriptors and
one listener.

If you are on 0.1.0, the fingerprint is a listener count near the fd limit:

```bash
docker exec <container> sh -c "awk 'NR>1 && \$4==\"0A\"' /proc/net/tcp | wc -l"
docker exec <container> sh -c 'ls /proc/1/fd | wc -l'
```

At rest the stale listeners cost nothing, so a snapshot taken while no client is
connecting looks innocent.

## Configuring a meter from compose

Every scalar in `sim/config.yaml` can be overridden with `SIM_<KEY>`, so you do
not need to mount a config file to change one number. The value is coerced to
the type already in the config, the effective value is logged at startup, and a
value that cannot be read is reported and ignored rather than silently dropped:

```
INFO  config override: nominal_current = 10.0 (was 5.0)
WARN  ignoring SIM_NOMINAL_CURRENT='zehn': cannot read it as float (keeping 5.0)
```

**To give an asset twice the power, double `nominal_current`** — power is
voltage x current x power factor, and the voltage is fixed at nominal:

```yaml
  energy-sim-big:
    image: skumh/modbus-energy-simulator:0.2.0
    environment:
      SIM_NOMINAL_CURRENT: "10"      # 5 A -> 10 A, so ~3.2 kW -> ~6.4 kW
    logging:
      driver: json-file
      options: { max-size: "10m", max-file: "3" }
```

Measured over 8 simulated hours: 5 A gives 3188 W, 10 A gives 6376 W (2.01x),
15 A gives 9516 W (3.00x).

**The power factor is not the knob for consumption.** It caps at 1.0, so from
the default 0.92 there is only 9% to gain; dropping it to 0.75 *lowers* active
power to 0.82x while the current stays put. Set `SIM_NOMINAL_POWER_FACTOR` when
you want a meter with a poor pf to look at, not to move the load.

Going past ~20 A also needs the walk band widened, and the simulator says so at
startup rather than quietly clamping:

```yaml
      SIM_NOMINAL_CURRENT: "15"
      SIM_CURRENT_MAX: "25"
```

### Why nominal_current only became a real knob in 0.2.0

Before 0.2.0 the current was a free random walk clamped to
`[current_min, current_max]`, with nothing pulling it back, so
`nominal_current` set the *first tick* and nothing else. Measured over 8 hours:
starting at 5 A the current wandered the whole band and averaged 6.2 A;
starting at 10 A it averaged 7.9 A with a standard deviation of 6.05 A. Two
meters configured differently were indistinguishable after an hour or two.

0.2.0 adds `current_pull` (default 0.02 per tick), a pull toward
`nominal_current`, which brings the standard deviation down to 0.58 A and makes
the mean sit on the configured value. Set `SIM_CURRENT_PULL=0` for the old
free-walk behaviour.
