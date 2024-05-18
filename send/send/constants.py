"""Immutable global data."""

from dataclasses import dataclass


@dataclass
class DMInfo:
    """Datamatrix info for a particular version of the symbol."""

    size: int
    raw_bytes: int
    zint_index: int

    @property
    def eci_bytes(self):
        return max(0, self.raw_bytes - 6)


dminfo = {
    10: DMInfo(size=10, raw_bytes=3, zint_index=1),
    12: DMInfo(size=12, raw_bytes=5, zint_index=2),
    14: DMInfo(size=14, raw_bytes=8, zint_index=3),
    16: DMInfo(size=16, raw_bytes=12, zint_index=4),
    18: DMInfo(size=18, raw_bytes=18, zint_index=5),
    20: DMInfo(size=20, raw_bytes=22, zint_index=6),
    22: DMInfo(size=22, raw_bytes=30, zint_index=7),
    24: DMInfo(size=24, raw_bytes=36, zint_index=8),
    26: DMInfo(size=26, raw_bytes=44, zint_index=9),
    32: DMInfo(size=32, raw_bytes=62, zint_index=10),
    36: DMInfo(size=36, raw_bytes=86, zint_index=11),
    40: DMInfo(size=40, raw_bytes=114, zint_index=12),
    44: DMInfo(size=44, raw_bytes=144, zint_index=13),
    48: DMInfo(size=48, raw_bytes=174, zint_index=14),
    52: DMInfo(size=52, raw_bytes=204, zint_index=15),
    64: DMInfo(size=64, raw_bytes=280, zint_index=16),
    72: DMInfo(size=72, raw_bytes=368, zint_index=17),
    80: DMInfo(size=80, raw_bytes=456, zint_index=18),
    88: DMInfo(size=88, raw_bytes=576, zint_index=19),
    96: DMInfo(size=96, raw_bytes=696, zint_index=20),
    104: DMInfo(size=104, raw_bytes=816, zint_index=21),
    120: DMInfo(size=120, raw_bytes=1050, zint_index=22),
    132: DMInfo(size=132, raw_bytes=1304, zint_index=23),
    144: DMInfo(size=144, raw_bytes=1558, zint_index=24),
}
"""A set of useful info about square datamatrix sizes, ordered by their sizes in dots."""

DatamatrixWidth = 96
ProtocolVersion = 2
LayerSize = dminfo[DatamatrixWidth].eci_bytes
PacketSize = LayerSize * 3
BlockSize = PacketSize - 6  # -6 for the block index at the beginning
HeaderPacketIndex = 0xFFFFFFFFFFFF  # max uint48
