# Copyright (C) 2023 Andrey Zhukov
#
# This file is part of the vis-transfer project, distributed under the GNU GPL version 3.
# For full terms see https://github.com/andreasxp/vis-transfer/blob/master/LICENSE.txt.
import base64
import hashlib
import json
import sys
from io import BytesIO

import cv2
from qreader import QReader


class DecodeError(RuntimeError):
    pass

# Precise decoder ======================================================================================================
_precise_reader = QReader()
def precise_decode(image):

    # Attempt 1: convert image as-is using the precise converter
    prepared_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    decoded_tuple = _precise_reader.detect_and_decode(prepared_image)
    if len(decoded_tuple) > 0 and decoded_tuple[0] is not None:
        return decoded_tuple[0]

    # Attempt 2: convert image to black and white using OTSU algorithm for threshold
    prepared_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    prepared_image = cv2.threshold(prepared_image, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    prepared_image = cv2.cvtColor(prepared_image, cv2.COLOR_GRAY2RGB)

    decoded_tuple = _precise_reader.detect_and_decode(prepared_image)
    if len(decoded_tuple) > 0 and decoded_tuple[0] is not None:
        return decoded_tuple[0]

    # Attempt 3: convert image to black and white using any threshold from 32 to 192 (16 increment)
    for threshold in range(32, 192+1, 16):
        prepared_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        prepared_image = cv2.threshold(prepared_image, threshold, 255, cv2.THRESH_BINARY)[1]
        prepared_image = cv2.cvtColor(prepared_image, cv2.COLOR_GRAY2RGB)

        decoded_tuple = _precise_reader.detect_and_decode(prepared_image)
        if len(decoded_tuple) > 0 and decoded_tuple[0] is not None:
            return decoded_tuple[0]

    return None

# Fast decoder =========================================================================================================
_fast_reader = cv2.QRCodeDetector()
def fast_decode(image):
    packet = _fast_reader.detectAndDecode(image)[0]

    if len(packet) == 0:
        return None

    return packet

# Qr code stream =======================================================================================================
class QrStream:
    def __init__(self, path):
        self.stream = cv2.VideoCapture(path)
        self.backup = []

        self.index = 0
        self.rewind_index = 0

    def __len__(self):
        return int(self.stream.get(cv2.CAP_PROP_FRAME_COUNT))

    def rewind(self):
        if self.rewind_index == 0:
            self.rewind_index = 1

    def confirm_ok(self):
        if self.rewind_index == 0:
            self.backup.clear()
        else:
            self.backup = self.backup[-self.rewind_index-1:]
            self.rewind_index = 0

    def next_frame(self):
        if self.rewind_index == 0:
            ok, image = self.stream.read()
            if not ok:
                raise DecodeError("end of file was reached before payload was received")

            self.backup.append(image)
            self.index += 1
            return image

        if self.rewind_index >= len(self.backup):
            raise DecodeError(f"failed to decode the stream at frame {self.index - self.rewind_index}")

        image = self.backup[-self.rewind_index-1]
        self.rewind_index += 1
        return image

    def next(self):
        if self.rewind_index == 0:
            return fast_decode(self.next_frame())

        return precise_decode(self.next_frame())


def print_status(stream, next_index, payload=None, payload_size=None):
    if stream.rewind_index == 0:
        status = "scanning "
    else:
        status = "rewinding"

    frame_index = stream.index - stream.rewind_index
    frame_total = len(stream)
    frame_percentage = (frame_index / frame_total) * 100
    frame_status = f"frame {frame_index}/{frame_total} ({frame_percentage:.2f}%)"

    if next_index is None:
        print(f"\r[{status}] {frame_status}; looking for header...", end="")
    else:
        payload_received = len(payload.getbuffer())
        payload_percentage = (payload_received / payload_size) * 100
        payload_status = f"payload bytes {payload_received}/{payload_size} ({payload_percentage:.2f}%)"

        print(f"\r[{status}] {frame_status}; {payload_status}; decoded {next_index-1} blocks", end="")


def decode(inpath, outpath):
    stream = QrStream(inpath)

    payload = BytesIO()

    # Find header
    while True:
        packet = stream.next()
        print_status(stream, None)

        try:
            metadata = json.loads(packet)
            size, sha = metadata["len"], metadata["sha"]
            stream.confirm_ok()
            break
        except (TypeError, ValueError):
            continue
    print(f"\nFound header: size={size}, sha256={sha}")

    # Find frames
    next_index = 0
    while True:
        print_status(stream, next_index, payload, size)
        packet = stream.next()

        try:
            index = int(packet[:10])
            block = packet[10:].encode("ascii")
        except (TypeError, ValueError):
            continue

        if index < next_index:
            stream.confirm_ok()
            continue

        if index > next_index:
            stream.rewind()
            continue

        payload.write(block)
        stream.confirm_ok()
        next_index += 1

        if len(payload.getbuffer()) > size:
            raise DecodeError("received payload of a bigger size than expected")

        if len(payload.getbuffer()) == size:
            break
    print()

    data = base64.b85decode(payload.getbuffer())

    m = hashlib.sha256()
    m.update(data)
    if m.hexdigest() != sha:
        raise DecodeError("SHA256 did not match")

    with open(outpath, "wb") as f:
        f.write(data)

def main():
    try:
        decode(sys.argv[1], sys.argv[2])
    except DecodeError as e:
        print(f"\nFailed to decode: {e}")

if __name__ == "__main__":
    sys.exit(main())
