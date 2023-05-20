import cv2
import json
import sys
import os
import base64
from qreader import QReader
from io import BytesIO
import hashlib

precise_reader = QReader()
def precise_decode(image):

    # Attempt 1: convert image as-is using the precise converter
    prepared_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    decoded_tuple = precise_reader.detect_and_decode(prepared_image)
    if len(decoded_tuple) > 0 and decoded_tuple[0] is not None:
        return decoded_tuple[0]

    # Attempt 2: convert image to black and white using OTSU algorithm for threshold
    prepared_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    prepared_image = cv2.threshold(prepared_image, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    prepared_image = cv2.cvtColor(prepared_image, cv2.COLOR_GRAY2RGB)

    decoded_tuple = precise_reader.detect_and_decode(prepared_image)
    if len(decoded_tuple) > 0 and decoded_tuple[0] is not None:
        return decoded_tuple[0]

    # Attempt 3: convert image to black and white using any threshold from 32 to 192 (16 increment)
    for threshold in range(32, 192+1, 16):
        prepared_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        prepared_image = cv2.threshold(prepared_image, threshold, 255, cv2.THRESH_BINARY)[1]
        prepared_image = cv2.cvtColor(prepared_image, cv2.COLOR_GRAY2RGB)

        decoded_tuple = precise_reader.detect_and_decode(prepared_image)
        if len(decoded_tuple) > 0 and decoded_tuple[0] is not None:
            return decoded_tuple[0]

    return None

fast_reader = cv2.QRCodeDetector()
def fast_decode(image):
    packet, bbox, _ = fast_reader.detectAndDecode(image)

    if len(packet) == 0:
        return None

    return packet

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
                raise RuntimeError("End of video file reached")

            self.backup.append(image)
            self.index += 1
            #print(f"\rFrame {self.index}/{len(self)}", end="")
            return image

        # print(f"\n\n{len(self.backup)}; {self.relative_index}")
        if self.rewind_index >= len(self.backup):
            raise RuntimeError("Failed to read stream")

        image = self.backup[-self.rewind_index-1]
        self.rewind_index += 1
        #print(f"\rFrame {self.index - self.rewind_index}/{len(self)} (Rewind)", end="")
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


def main():
    stream = QrStream(sys.argv[1])

    payload = BytesIO()

    # Find header
    while(True):
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
    while(True):
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
            #print(f"\nFailed to find block {next_index}: got {index}; rewinding...")
            stream.rewind()
            continue

        payload.write(block)
        if len(payload.getbuffer()) > size:
            print("len > size")
            break
            #payload = payload[:size]

        if len(payload.getbuffer()) == size:
            break
        #print(f"; Block {next_index}", end="")
        stream.confirm_ok()
        next_index += 1
    print()

    data = base64.b85decode(payload.getbuffer()[:size])

    m = hashlib.sha256()
    m.update(data)
    print(m.hexdigest())
    print(sha)

    with open(sys.argv[2], "wb") as f:
        f.write(data)

if __name__ == "__main__":
    sys.exit(main())
