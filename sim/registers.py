"""Encoders for packing float32 / uint32 into 16-bit Modbus register pairs.

Word order is big-endian (ABCD): high word at the lower address.
"""

import struct


def float32_to_regs(value: float) -> tuple[int, int]:
    packed = struct.pack(">f", float(value))
    hi, lo = struct.unpack(">HH", packed)
    return hi, lo


def u32_to_regs(value: int) -> tuple[int, int]:
    v = int(value) & 0xFFFFFFFF
    return (v >> 16) & 0xFFFF, v & 0xFFFF


def regs_to_float32(hi: int, lo: int) -> float:
    packed = struct.pack(">HH", hi & 0xFFFF, lo & 0xFFFF)
    return struct.unpack(">f", packed)[0]


def regs_to_u32(hi: int, lo: int) -> int:
    return ((hi & 0xFFFF) << 16) | (lo & 0xFFFF)
