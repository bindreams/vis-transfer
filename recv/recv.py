# Copyright (C) 2023 Andrey Zhukov
#
# This file is part of the vis-transfer project, distributed under the GNU GPL version 3.
# For full terms see https://github.com/andreasxp/vis-transfer/blob/master/LICENSE.txt.
import base64
import hashlib
import json
import sys
from io import BytesIO
import pyzbar_patch as pyzbar
import math
from precise_reader import QReader

import cv2


class DecodeError(RuntimeError):
    pass

class DecodeEofError(DecodeError):
    pass

# Precise decoder ======================================================================================================
_precise_reader = QReader()
def precise_decode_single_channel(input):
    # Attempt 1: convert image as-is using the precise converter
    image = input
    image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    qrs = _precise_reader.detect_and_decode(image)
    if len(qrs) > 0 and qrs[0] is not None:
        return qrs[0]

    # Attempt 2: convert image to black and white using OTSU algorithm for threshold
    image = input
    image = cv2.threshold(image, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)

    qrs = _precise_reader.detect_and_decode(image)
    if len(qrs) > 0 and qrs[0] is not None:
        return qrs[0]

    # Attempt 3: convert image to black and white using any threshold from 32 to 192 (16 increment)
    for threshold in range(32, 192+1, 16):
        image = input
        #image = cv2.threshold(image, threshold, 255, cv2.THRESH_BINARY)[1]
        image = cv2.GaussianBlur(src=image, ksize=(3, 3), sigmaX=0)
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)

        qrs = _precise_reader.detect_and_decode(image)
        if len(qrs) > 0 and qrs[0] is not None:
            return qrs[0]

    return None

def precise_decode(image):
    b,g,r = cv2.split(image)

    packet_parts = []
    for i in (r,g,b):
        packet_part = precise_decode_single_channel(i)
        if packet_part is None:
            return None

        packet_parts.append(packet_part)

    return b"".join(packet_parts)


# Fast decoder =========================================================================================================
def bbox_to_rect(image, bbox):
    bbox = bbox[0]

    xs = [bbox[i][0] for i in range(4)]
    ys = [bbox[i][1] for i in range(4)]

    x1 = min(math.floor(min(xs)), 0)
    y1 = min(math.floor(min(ys)), 0)

    height, width, _ = image.shape

    x2 = max(math.ceil(max(xs)), width)
    y2 = max(math.ceil(max(ys)), height)

    return (x1, y1, x2, y2)

_fast_decoder = cv2.QRCodeDetector()
def fast_decode(image):
    b,g,r = cv2.split(image)

    packet = BytesIO()
    read_empty = False

    for i in (r, g, b):
        ok, bbox = _fast_decoder.detect(i)
        if not ok:
            return None

        image = cv2.cvtColor(i, cv2.COLOR_GRAY2RGB)
        qr = _precise_reader.decode(image, bbox_to_rect(image, bbox))

        if qr is None:
            read_empty = True
            continue

        if read_empty:
            # Previously read an empty block, and now we have bytes: this is a read error
            return None

        packet.write(qr)

    return packet.getvalue()


# Qr code stream =======================================================================================================
class QrStream:
    def __init__(self, path):
        self.stream = cv2.VideoCapture(path)
        self.backup = []

        self.head = 0
        self.pos = 0

        self._defaultmode = 0
        self.mode = self._defaultmode
        self.maxmode = 1

    def __len__(self):
        return int(self.stream.get(cv2.CAP_PROP_FRAME_COUNT))

    @property
    def defaultmode(self):
        return self._defaultmode

    @defaultmode.setter
    def defaultmode(self, value):
        if value > self.maxmode:
            raise RuntimeError("Default mode cannot be higher than max mode")

        self._defaultmode = value
        self.mode = max(self.mode, value)

    def rewind(self):
        if self.mode == self.maxmode:
            raise DecodeError(f"failed to decode the stream at frame {self.pos}")

        self.mode += 1
        self.pos = self.head - len(self.backup)

    def confirm_ok(self):
        if self.pos == self.head:
            self.backup.clear()
            self.mode = self._defaultmode

        self.backup = self.backup[-(self.head - self.pos):]

    def next_frame(self):
        if self.pos == self.head:
            ok, image = self.stream.read()
            if not ok:
                raise DecodeEofError("end of file was reached before payload was received")

            self.backup.append(image)
            self.head += 1
            self.pos += 1
            return image

        image = self.backup[-(self.head - self.pos)]
        self.pos += 1
        return image

    def next(self):
        if self.mode == 0:
            return fast_decode(self.next_frame())

        return precise_decode(self.next_frame())


def print_status(stream, next_index, payload=None, payload_size=None):
    if stream.pos == stream.head:
        status = "scanning "
    else:
        status = "rewinding"

    frame_index = stream.pos
    frame_total = len(stream)
    frame_percentage = (frame_index / frame_total) * 100
    frame_status = f"frame {frame_index}/{frame_total} ({frame_percentage:.2f}%)"

    if next_index is None:
        print(f"\r[{status}] {frame_status}; looking for header...", end="")
    else:
        payload_received = len(payload.getbuffer())
        payload_percentage = (payload_received / payload_size) * 100
        payload_status = f"payload bytes {payload_received}/{payload_size} ({payload_percentage:.2f}%)"

        print(f"\r[{status}] {frame_status}; {payload_status}; decoded {next_index} blocks", end="")

def decode(inpath, outpath):
    stream = QrStream(inpath)

    payload = BytesIO()

    # Find header
    stream.defaultmode = 1
    while True:
        packet = stream.next()
        print_status(stream, None)

        try:
            metadata = json.loads(packet.decode("ascii"))
            size, sha = metadata["len"], metadata["sha"]
            stream.confirm_ok()
            break
        except (TypeError, ValueError):
            continue
    print(f"\nFound header: size={size}, sha256={sha}")

    # Find frames
    next_index = 0
    last_packet_size = None
    stream.defaultmode = 0
    stream.mode = 0
    while True:
        print_status(stream, next_index, payload, size)
        try:
            packet = stream.next()
        except DecodeEofError:
            stream.rewind()
            continue

        try:
            index = int(packet[:10].decode("ascii"))
            block = packet[10:]
        except (TypeError, ValueError):
            continue

        if index < next_index:
            stream.confirm_ok()
            continue

        if index > next_index:
            stream.rewind()
            continue

        if (last_packet_size is not None and
            len(packet) < last_packet_size and
            len(payload.getbuffer()) + len(block) != size):
            # Block too small: likely a decoding error
            continue

        payload.write(block)
        stream.confirm_ok()
        last_packet_size = len(packet)
        next_index += 1

        if len(payload.getbuffer()) > size:
            raise DecodeError("received payload of a bigger size than expected")

        if len(payload.getbuffer()) == size:
            break

    payload = payload.getvalue()
    m = hashlib.sha256()
    m.update(payload)
    if m.hexdigest() != sha:
        raise DecodeError("SHA256 did not match")

    with open(outpath, "wb") as f:
        f.write(payload)

def main():
    try:
        decode(sys.argv[1], sys.argv[2])
    except DecodeError as e:
        print(f"\nFailed to decode: {e}")

if __name__ == "__main__":
    sys.exit(main())
