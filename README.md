# Modbus Energy Simulator

[![Docker Pulls](https://img.shields.io/docker/pulls/skumh/modbus-energy-simulator)](https://hub.docker.com/r/skumh/modbus-energy-simulator)
[![Docker Image Version](https://img.shields.io/docker/v/skumh/modbus-energy-simulator?sort=semver)](https://hub.docker.com/r/skumh/modbus-energy-simulator/tags)

A small Docker container that simulates a 3-phase energy meter, over
**Modbus TCP** or **OPC UA**. Use it during benthos-umh / UMH development, demos
and workshops when you don't have a real meter on the bench.

Both images run the same meter model (`sim/model.py`) and expose the same 40
data points (`sim/points.py`): phase and line voltages, phase and neutral
currents, active / reactive / apparent power and power factor per phase and in
total, 15-min demand, four energy counters, frequency and THD.

Published images (multi-arch, `linux/amd64` + `linux/arm64`):

```
docker pull skumh/modbus-energy-simulator:0.3.0
docker pull skumh/opcua-energy-simulator:0.3.0
```

## Quick start — just the simulator

```bash
docker run --rm -p 1502:1502 skumh/modbus-energy-simulator:0.3.0
docker run --rm -p 4840:4840 skumh/opcua-energy-simulator:0.3.0
```

The Modbus simulator listens on `tcp://localhost:1502` (slave ID 1, big-endian
word order), the OPC UA simulator on `opc.tcp://localhost:4840` (security None,
anonymous).

## Quick start — with benthos-umh + UMH Core

The included `docker-compose.yml` brings up the simulator side-by-side with
benthos-umh / UMH Core (`umh-core`). Within a few seconds you should see
decoded JSON messages flowing through the bridge.

```bash
docker compose up
```

Replace `AUTH_TOKEN` in `docker-compose.yml` with your own UMH Core token
before starting (`docker compose down` to tear down).

## Register map (Modbus)

Slave ID `1`, all values in **holding registers** (function code `0x03`), byte
order `ABCD` (big-endian). FLOAT32 / UINT32 span two consecutive registers.
Addresses 0-33 and 100 are unchanged since 0.1.0; 0.3.0 only adds registers.
Generated with `python -m sim.docs modbus`.

| Address | Type | Tag | Unit | Description |
|--|--|--|--|--|
| 0 | FLOAT32 | voltage_l1 | V | Phase voltage L1-N |
| 2 | FLOAT32 | voltage_l2 | V | Phase voltage L2-N |
| 4 | FLOAT32 | voltage_l3 | V | Phase voltage L3-N |
| 6 | FLOAT32 | current_l1 | A | Phase current L1 |
| 8 | FLOAT32 | current_l2 | A | Phase current L2 |
| 10 | FLOAT32 | current_l3 | A | Phase current L3 |
| 12 | FLOAT32 | power_active_total | W | Active power, sum L1-L3 |
| 14 | FLOAT32 | power_reactive_total | var | Reactive power, sum L1-L3 |
| 16 | FLOAT32 | power_apparent_total | VA | Apparent power, sqrt(P^2 + Q^2) |
| 18 | FLOAT32 | power_factor | - | Total power factor, P / S |
| 20 | FLOAT32 | frequency | Hz | Grid frequency |
| 22 | FLOAT32 | voltage_l1_l2 | V | Line voltage L1-L2 |
| 24 | FLOAT32 | voltage_l2_l3 | V | Line voltage L2-L3 |
| 26 | FLOAT32 | voltage_l3_l1 | V | Line voltage L3-L1 |
| 28 | FLOAT32 | current_n | A | Neutral current (vector sum of L1-L3) |
| 30 | UINT32 | energy_active_import | Wh | Active energy, import (counter) |
| 32 | UINT32 | energy_active_export | Wh | Active energy, export (counter) |
| 34 | UINT32 | energy_reactive_import | varh | Reactive energy, import (counter) |
| 36 | UINT32 | energy_apparent | VAh | Apparent energy (counter) |
| 40 | FLOAT32 | power_active_l1 | W | Active power L1 |
| 42 | FLOAT32 | power_active_l2 | W | Active power L2 |
| 44 | FLOAT32 | power_active_l3 | W | Active power L3 |
| 46 | FLOAT32 | power_reactive_l1 | var | Reactive power L1 |
| 48 | FLOAT32 | power_reactive_l2 | var | Reactive power L2 |
| 50 | FLOAT32 | power_reactive_l3 | var | Reactive power L3 |
| 52 | FLOAT32 | power_apparent_l1 | VA | Apparent power L1 |
| 54 | FLOAT32 | power_apparent_l2 | VA | Apparent power L2 |
| 56 | FLOAT32 | power_apparent_l3 | VA | Apparent power L3 |
| 58 | FLOAT32 | power_factor_l1 | - | Power factor L1 |
| 60 | FLOAT32 | power_factor_l2 | - | Power factor L2 |
| 62 | FLOAT32 | power_factor_l3 | - | Power factor L3 |
| 64 | FLOAT32 | thd_voltage_l1 | % | Total harmonic distortion, voltage L1 |
| 66 | FLOAT32 | thd_voltage_l2 | % | Total harmonic distortion, voltage L2 |
| 68 | FLOAT32 | thd_voltage_l3 | % | Total harmonic distortion, voltage L3 |
| 70 | FLOAT32 | thd_current_l1 | % | Total harmonic distortion, current L1 |
| 72 | FLOAT32 | thd_current_l2 | % | Total harmonic distortion, current L2 |
| 74 | FLOAT32 | thd_current_l3 | % | Total harmonic distortion, current L3 |
| 76 | FLOAT32 | power_active_demand | W | Average active power over the demand window (default 15 min) |
| 78 | FLOAT32 | power_active_demand_max | W | Highest demand value since start |
| 100 | UINT16 | status | bits | b0 = online (always 1), b1 = alarm (toggles every 60 s) |

## Node list (OPC UA)

Endpoint `opc.tcp://<host>:4840` (no path), security None, anonymous. All
variables sit flat below the object `EM_01` (`ns=2;i=5000`), namespace URI
`urn:umh:energy-meter-simulator` (index 2). Generated with
`python -m sim.docs opcua`.

**The node IDs are numeric and the browse names are short codes on purpose**,
and the nodes carry no description. That is what OPC UA servers on PLCs and
many meters look like: you only learn what `ns=2;i=6100` is from the vendor
documentation. In benthos-umh the tag name is the browse name (`P_SUM`).

| NodeId | Browse name | Data type | Unit | Description |
|--|--|--|--|--|
| `ns=2;i=6011` | U_L1N | Double | V | Phase voltage L1-N |
| `ns=2;i=6012` | U_L2N | Double | V | Phase voltage L2-N |
| `ns=2;i=6013` | U_L3N | Double | V | Phase voltage L3-N |
| `ns=2;i=6021` | U_L12 | Double | V | Line voltage L1-L2 |
| `ns=2;i=6022` | U_L23 | Double | V | Line voltage L2-L3 |
| `ns=2;i=6023` | U_L31 | Double | V | Line voltage L3-L1 |
| `ns=2;i=6031` | I_L1 | Double | A | Phase current L1 |
| `ns=2;i=6032` | I_L2 | Double | A | Phase current L2 |
| `ns=2;i=6033` | I_L3 | Double | A | Phase current L3 |
| `ns=2;i=6034` | I_N | Double | A | Neutral current (vector sum of L1-L3) |
| `ns=2;i=6100` | P_SUM | Double | W | Active power, sum L1-L3 |
| `ns=2;i=6101` | P_L1 | Double | W | Active power L1 |
| `ns=2;i=6102` | P_L2 | Double | W | Active power L2 |
| `ns=2;i=6103` | P_L3 | Double | W | Active power L3 |
| `ns=2;i=6110` | Q_SUM | Double | var | Reactive power, sum L1-L3 |
| `ns=2;i=6111` | Q_L1 | Double | var | Reactive power L1 |
| `ns=2;i=6112` | Q_L2 | Double | var | Reactive power L2 |
| `ns=2;i=6113` | Q_L3 | Double | var | Reactive power L3 |
| `ns=2;i=6120` | S_SUM | Double | VA | Apparent power, sqrt(P^2 + Q^2) |
| `ns=2;i=6121` | S_L1 | Double | VA | Apparent power L1 |
| `ns=2;i=6122` | S_L2 | Double | VA | Apparent power L2 |
| `ns=2;i=6123` | S_L3 | Double | VA | Apparent power L3 |
| `ns=2;i=6130` | PF_SUM | Double | - | Total power factor, P / S |
| `ns=2;i=6131` | PF_L1 | Double | - | Power factor L1 |
| `ns=2;i=6132` | PF_L2 | Double | - | Power factor L2 |
| `ns=2;i=6133` | PF_L3 | Double | - | Power factor L3 |
| `ns=2;i=6201` | P_DMD | Double | W | Average active power over the demand window (default 15 min) |
| `ns=2;i=6202` | P_DMD_MAX | Double | W | Highest demand value since start |
| `ns=2;i=6301` | F | Double | Hz | Grid frequency |
| `ns=2;i=6311` | THDU_L1 | Double | % | Total harmonic distortion, voltage L1 |
| `ns=2;i=6312` | THDU_L2 | Double | % | Total harmonic distortion, voltage L2 |
| `ns=2;i=6313` | THDU_L3 | Double | % | Total harmonic distortion, voltage L3 |
| `ns=2;i=6321` | THDI_L1 | Double | % | Total harmonic distortion, current L1 |
| `ns=2;i=6322` | THDI_L2 | Double | % | Total harmonic distortion, current L2 |
| `ns=2;i=6323` | THDI_L3 | Double | % | Total harmonic distortion, current L3 |
| `ns=2;i=7001` | EP_IMP | Double | Wh | Active energy, import (counter) |
| `ns=2;i=7002` | EP_EXP | Double | Wh | Active energy, export (counter) |
| `ns=2;i=7003` | EQ_IMP | Double | varh | Reactive energy, import (counter) |
| `ns=2;i=7004` | ES | Double | VAh | Apparent energy (counter) |
| `ns=2;i=9001` | STATUS | UInt16 | bits | b0 = online (always 1), b1 = alarm (toggles every 60 s) |

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
    image: skumh/modbus-energy-simulator:0.3.0
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

### Presets for a few machine types

`P = (V1 x I1 + V2 x I2 + V3 x I3) x pf`, so at 3 x 230 V and pf 0.92 one amp is
about 635 W, and `I = P / (3 x 230 x pf)`. Measured over 8 simulated hours:

| Machine | `SIM_NOMINAL_CURRENT` | `SIM_NOMINAL_POWER_FACTOR` | `SIM_CURRENT_MAX` | `SIM_CURRENT_WALK_STEP` | gives |
|---|---|---|---|---|---|
| 5-axis machining centre | 17 | 0.90 | 30 | 0.5 | 10.5 kW (8.4-12.5) |
| Parts washer | 32 | 0.93 | 50 | 0.9 | 20.5 kW (16.8-24.3) |
| Hardening furnace | 63 | 0.99 | 90 | 1.8 | 42.8 kW (36.1-50.7) |

Typical *operating* draw, not connected load — a 5-axis centre of that class is
20-40 kVA installed but averages 8-15 kW while machining, and an electric
hardening furnace is 60-150 kVA installed and averages 30-50 kW. The power
factors are the physics: variable-frequency drives on the machining centre,
essentially resistive heating in the furnace.

`SIM_CURRENT_MAX` has to clear the nominal or the walk is clamped to the default
20 A band. `SIM_CURRENT_WALK_STEP` scales with it: the standard deviation is
about 2.9 x the step, so a proportional step keeps the relative wobble the same
across machines -- left at the default the furnace at 63 A is almost a flat
line.

**These are averages, not load profiles.** A real machining centre sits at
2-4 kW between parts and jumps to 12-15 kW in the cut; a furnace ramps near
full power and drops to a fraction of it while soaking. By default the
simulator wobbles smoothly around one mean. Since 0.3.0 `SIM_LOAD_PROFILE=machine`
alternates production (at `nominal_current`) and idle (at `idle_load_factor` x
nominal, default 0.25) with random durations (`production_min/max_seconds`,
`idle_min/max_seconds`), which gives a dashboard visible steps and an alert
something to fire on. It is still no ramp/soak model.

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

## Tests

```bash
pip install "pymodbus==3.8.*" "asyncua==1.1.*" pyyaml pytest
pytest tests/test_model.py                      # physics: phase sums, power triangle, counters, demand
python -m sim.server & python tests/client_smoke.py
python -m sim.opcua_server & python tests/opcua_smoke.py
```

## Changelog

- **0.3.0**: full 3-phase point set (per-phase P/Q/S/pf, line voltages, neutral
  current, reactive and apparent energy, 15-min demand, THD); OPC UA server on
  the same model (`skumh/opcua-energy-simulator`); `load_profile: machine`. The
  total power factor is now P / S of the three phases (each phase has its own
  pf). Modbus addresses of 0.2.0 are unchanged.
- **0.2.0**: `SIM_<KEY>` overrides; `current_pull` makes `nominal_current` a real knob.
- **0.1.1**: pymodbus 3.8, fixes the listening-socket leak.
