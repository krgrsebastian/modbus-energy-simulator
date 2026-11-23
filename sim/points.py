"""The meter's data points: one table, read by both servers, the tests and the docs.

Every point has one value in the model snapshot (keyed by `name`), one Modbus
holding-register address and one OPC UA node. Adding a point here is the only
change needed to expose it on both protocols.

Modbus: holding registers (FC 0x03), byte and word order ABCD (big-endian).
FLOAT32 and UINT32 span two registers. Addresses 0..33 and 100 are unchanged
since 0.1.0, so existing bridges keep working.

OPC UA: numeric NodeIds `ns=2;i=<id>` below the object EM_01, browse names are
short vendor codes (P_SUM, EP_IMP, ...) and the nodes carry no description, like
many real meters: what a node means is only in the vendor documentation. All
values Double except STATUS (UInt16). Same units as Modbus.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Point:
    name: str          # key in the model snapshot, and the Modbus tag name
    modbus_addr: int
    modbus_type: str   # FLOAT32 | UINT32 | UINT16
    opcua_id: int      # numeric NodeId: ns=2;i=<opcua_id>
    opcua_name: str    # browse/display name, a vendor-style short code
    unit: str
    description: str

    @property
    def node_id(self) -> str:
        return f"ns=2;i={self.opcua_id}"


POINTS: list[Point] = [
    # --- voltage ---
    Point("voltage_l1", 0, "FLOAT32", 6011, "U_L1N", "V", "Phase voltage L1-N"),
    Point("voltage_l2", 2, "FLOAT32", 6012, "U_L2N", "V", "Phase voltage L2-N"),
    Point("voltage_l3", 4, "FLOAT32", 6013, "U_L3N", "V", "Phase voltage L3-N"),
    Point("voltage_l1_l2", 22, "FLOAT32", 6021, "U_L12", "V", "Line voltage L1-L2"),
    Point("voltage_l2_l3", 24, "FLOAT32", 6022, "U_L23", "V", "Line voltage L2-L3"),
    Point("voltage_l3_l1", 26, "FLOAT32", 6023, "U_L31", "V", "Line voltage L3-L1"),
    # --- current ---
    Point("current_l1", 6, "FLOAT32", 6031, "I_L1", "A", "Phase current L1"),
    Point("current_l2", 8, "FLOAT32", 6032, "I_L2", "A", "Phase current L2"),
    Point("current_l3", 10, "FLOAT32", 6033, "I_L3", "A", "Phase current L3"),
    Point("current_n", 28, "FLOAT32", 6034, "I_N", "A", "Neutral current (vector sum of L1-L3)"),
    # --- active power ---
    Point("power_active_l1", 40, "FLOAT32", 6101, "P_L1", "W", "Active power L1"),
    Point("power_active_l2", 42, "FLOAT32", 6102, "P_L2", "W", "Active power L2"),
    Point("power_active_l3", 44, "FLOAT32", 6103, "P_L3", "W", "Active power L3"),
    Point("power_active_total", 12, "FLOAT32", 6100, "P_SUM", "W", "Active power, sum L1-L3"),
    # --- reactive power ---
    Point("power_reactive_l1", 46, "FLOAT32", 6111, "Q_L1", "var", "Reactive power L1"),
    Point("power_reactive_l2", 48, "FLOAT32", 6112, "Q_L2", "var", "Reactive power L2"),
    Point("power_reactive_l3", 50, "FLOAT32", 6113, "Q_L3", "var", "Reactive power L3"),
    Point("power_reactive_total", 14, "FLOAT32", 6110, "Q_SUM", "var", "Reactive power, sum L1-L3"),
    # --- apparent power ---
    Point("power_apparent_l1", 52, "FLOAT32", 6121, "S_L1", "VA", "Apparent power L1"),
    Point("power_apparent_l2", 54, "FLOAT32", 6122, "S_L2", "VA", "Apparent power L2"),
    Point("power_apparent_l3", 56, "FLOAT32", 6123, "S_L3", "VA", "Apparent power L3"),
    Point("power_apparent_total", 16, "FLOAT32", 6120, "S_SUM", "VA", "Apparent power, sqrt(P^2 + Q^2)"),
    # --- power factor ---
    Point("power_factor_l1", 58, "FLOAT32", 6131, "PF_L1", "-", "Power factor L1"),
    Point("power_factor_l2", 60, "FLOAT32", 6132, "PF_L2", "-", "Power factor L2"),
    Point("power_factor_l3", 62, "FLOAT32", 6133, "PF_L3", "-", "Power factor L3"),
    Point("power_factor", 18, "FLOAT32", 6130, "PF_SUM", "-", "Total power factor, P / S"),
    # --- demand ---
    Point("power_active_demand", 76, "FLOAT32", 6201, "P_DMD", "W", "Average active power over the demand window (default 15 min)"),
    Point("power_active_demand_max", 78, "FLOAT32", 6202, "P_DMD_MAX", "W", "Highest demand value since start"),
    # --- energy ---
    Point("energy_active_import", 30, "UINT32", 7001, "EP_IMP", "Wh", "Active energy, import (counter)"),
    Point("energy_active_export", 32, "UINT32", 7002, "EP_EXP", "Wh", "Active energy, export (counter)"),
    Point("energy_reactive_import", 34, "UINT32", 7003, "EQ_IMP", "varh", "Reactive energy, import (counter)"),
    Point("energy_apparent", 36, "UINT32", 7004, "ES", "VAh", "Apparent energy (counter)"),
    # --- power quality ---
    Point("frequency", 20, "FLOAT32", 6301, "F", "Hz", "Grid frequency"),
    Point("thd_voltage_l1", 64, "FLOAT32", 6311, "THDU_L1", "%", "Total harmonic distortion, voltage L1"),
    Point("thd_voltage_l2", 66, "FLOAT32", 6312, "THDU_L2", "%", "Total harmonic distortion, voltage L2"),
    Point("thd_voltage_l3", 68, "FLOAT32", 6313, "THDU_L3", "%", "Total harmonic distortion, voltage L3"),
    Point("thd_current_l1", 70, "FLOAT32", 6321, "THDI_L1", "%", "Total harmonic distortion, current L1"),
    Point("thd_current_l2", 72, "FLOAT32", 6322, "THDI_L2", "%", "Total harmonic distortion, current L2"),
    Point("thd_current_l3", 74, "FLOAT32", 6323, "THDI_L3", "%", "Total harmonic distortion, current L3"),
    # --- status ---
    Point("status", 100, "UINT16", 9001, "STATUS", "bits", "b0 = online (always 1), b1 = alarm (toggles every 60 s)"),
]

REGISTER_WIDTH = {"FLOAT32": 2, "UINT32": 2, "UINT16": 1}
