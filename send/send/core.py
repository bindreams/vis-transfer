import hashlib
import io
import itertools
import math
import os
import struct
from dataclasses import dataclass
from typing import BinaryIO

from PIL import Image
from zint import InputMode, Symbol, Symbology

from . import constants
from .constants import dminfo


def datamatrix(data: bytes, /, *, symbol_size: int):
    """Produce a PIL.Image of a single-channel grayscale datamatrix containing `data`."""
    if len(data) > dminfo[symbol_size].eci_bytes:
        raise ValueError(
            f"data length {len(data)} is too big to fit into a datamatrix of size "
            f"{symbol_size}x{symbol_size} (max allowed size is {dminfo[symbol_size].eci_bytes})"
        )

    symbol = Symbol()
    symbol.symbology = Symbology.DATAMATRIX
    symbol.input_mode |= InputMode.FAST
    symbol.option_2 = dminfo[symbol_size].zint_index
    symbol.encode(data)
    symbol.buffer()

    return Image.frombytes("RGB", symbol.bitmap.shape[:-1], symbol.bitmap, "raw").convert("L")


def dense_datamatrix(data: tuple[bytes, bytes, bytes], /, *, symbol_size: int):
    """Produce a PIL.Image of a dense datamatrix (3 color channels for 3 datamatrices) containing `data`."""
    submatrices = []

    for layer, i in zip(data, itertools.count()):
        if len(layer) > dminfo[symbol_size].eci_bytes:
            raise ValueError(
                f"size of layer {i} ({len(data)}B) is too big to fit into a datamatrix of size "
                f"{symbol_size}x{symbol_size} (max allowed size is {dminfo[symbol_size].eci_bytes})"
            )

        submatrices.append(datamatrix(layer, symbol_size=symbol_size))

    return Image.merge("RGB", submatrices)


def ddm_stream(fd: BinaryIO, /, *, symbol_size: int):
    """Given a binary stream `f`, yield sequential dense datamatrix encodings of the file."""
    packet_size = dminfo[symbol_size].eci_bytes * 3
    for packet in packet_stream(fd, packet_size=packet_size):
        yield dense_datamatrix(packet, symbol_size=symbol_size)


def ddm_stream_header(fd: BinaryIO, /, *, symbol_size: int):
    """Given a seekable stream, produce a header dense datamatrix."""
    packet_size = dminfo[symbol_size].eci_bytes * 3
    packet = packet_stream_header(fd, packet_size=packet_size)
    return dense_datamatrix(packet, symbol_size=symbol_size)


def packet_stream(fd: BinaryIO, /, *, packet_size: int):
    """Given a binary stream `f`, yield sequential packets to be encoded and sent."""
    # A block is a section of the payload that fits into one packet.
    # Its size is the packet size minus 6 bytes for the index.
    block_size = packet_size - 6

    for i in itertools.count():
        if i >= constants.HeaderPacketIndex:
            raise ValueError("stream is too big; index has overflown")

        block = fd.read(block_size)
        assert block is not None
        if len(block) == 0:
            break

        yield makepacket(i, block, packet_size=packet_size)


@dataclass
class PacketStreamInfo:
    file_size: int
    sha3_256: bytes


def packet_stream_header(file_info_or_fd: BinaryIO | PacketStreamInfo, packet_size: int) -> tuple[bytes, bytes, bytes]:
    """Given a seekable stream or PacketStreamInfo and target packet size, produce a header packet."""
    if not isinstance(file_info_or_fd, PacketStreamInfo):
        file_info = packet_stream_info(file_info_or_fd)
    else:
        file_info = file_info_or_fd

    block = struct.pack(  # Similar to live packets, the index is not considered part of payload and is added later
        ">HQH32s",
        constants.ProtocolVersion,  # protocol version
        file_info.file_size,  # file size
        packet_size,  # packet size
        file_info.sha3_256,  # sha3-256 of file
    )

    return makepacket(index=constants.HeaderPacketIndex, block=block, packet_size=packet_size)


def packet_stream_info(fd: BinaryIO):
    """Retrieve necessary information to assemble a packet stream header."""
    old_pos = fd.tell()

    try:
        fd.seek(0, os.SEEK_END)
        size = fd.tell()
        fd.seek(0, os.SEEK_SET)
    except OSError as e:
        raise ValueError("provided stream is not seekable") from e

    hasher = hashlib.sha3_256()
    while True:
        section = fd.read(65536)
        assert section is not None  # Probably can't happen since we just seeked to SEEK_END
        if len(section) == 0:
            break
        hasher.update(section)

    fd.seek(old_pos, os.SEEK_SET)
    sha3_256 = hasher.digest()
    return PacketStreamInfo(size, sha3_256)


def packet_count(file_info_or_fd: BinaryIO | PacketStreamInfo):
    if not isinstance(file_info_or_fd, PacketStreamInfo):
        file_info = packet_stream_info(file_info_or_fd)
    else:
        file_info = file_info_or_fd

    return math.ceil(file_info.file_size / constants.BlockSize)


def makepacket(index: int, block: bytes, *, packet_size: int) -> tuple[bytes, bytes, bytes]:
    """Combine the index and the block to produce a packet.

    Returns a tuple of three bytes objects because the packet will be spliced across three channels.
    """
    block_size = packet_size - 6
    if len(block) > block_size:
        raise ValueError(f"block size {len(block)} is too large to fit into a packet of size {packet_size}")

    packed_index = encodeindex(index)

    # When creating a packet, the index is spliced across all three layers, so that a packet cannot be accidentally
    # partially scanned and none of the layers are empty.
    return (
        packed_index[0:2] + block[0 * (block_size // 3) : 1 * (block_size // 3)],
        packed_index[2:4] + block[1 * (block_size // 3) : 2 * (block_size // 3)],
        packed_index[4:6] + block[2 * (block_size // 3) : 3 * (block_size // 3)],
    )


def encodeindex(index: int):
    if index > constants.HeaderPacketIndex:
        raise ValueError(f"index {index} is too big to fit into 6 bytes")

    # Pack as a uint64 and cut off top 2 bytes to get a 6-byte index
    return struct.pack(">Q", index)[2:]
