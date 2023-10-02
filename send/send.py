# Copyright (C) 2023 Andrey Zhukov
#
# This file is part of the vis-transfer project, distributed under the GNU GPL version 3.
# For full terms see https://github.com/andreasxp/vis-transfer/blob/master/LICENSE.md.
import hashlib
import sys
import os
import math
import struct
import io

from PIL import Image
from PIL.ImageQt import ImageQt
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication, QLabel, QFileDialog, QVBoxLayout, QWidget, QHBoxLayout, QProgressBar, QPushButton, QStackedWidget, QSizePolicy
)
import pyzint


def datamatrix(data, /, *, version):
    bmp_string = pyzint.Barcode.DATAMATRIX(data, option_2=version).render_bmp()
    return Image.open(io.BytesIO(bmp_string), formats=("BMP",)).convert("L")


LAYER_SIZE = 690
PACKET_SIZE = LAYER_SIZE * 3
BLOCK_SIZE = PACKET_SIZE - 6  # -6 for the block index at the beginning
HEADER_PACKET_INDEX = 0xFFFFFFFFFFFF  # max uint48


def packet_image(data, size: int):
    #print("data:", repr(data))
    assert len(data) <= PACKET_SIZE
    index = data[:6]
    payload = data[6:]

    data = (
        index[0:2] + payload[0*(BLOCK_SIZE//3):1*(BLOCK_SIZE//3)],
        index[2:4] + payload[1*(BLOCK_SIZE//3):2*(BLOCK_SIZE//3)],
        index[4:6] + payload[2*(BLOCK_SIZE//3):3*(BLOCK_SIZE//3)],
    )

    subpacket_images = []
    for i in range(3):
        subpacket_images.append(datamatrix(data[i], version=20))

    result = Image.merge("RGB", subpacket_images)
    result = result.resize((size, size), Image.Resampling.NEAREST)
    return QPixmap(ImageQt(result))


def encodeindex(index):
    return struct.pack(">Q", index)[2:]

class SendWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color:white;")

        ly = QVBoxLayout()
        self.setLayout(ly)

        self.setContentsMargins(0, 0, 0, 0)
        ly.setContentsMargins(0, 0, 0, 0)

        self.wImage = QLabel()
        self.wImage.setMinimumSize(96, 96)
        self.wImage.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.wImage.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.wProgressBar = QProgressBar()
        self.wBlockCount = QLabel()

        wInstructions = QLabel("Start your recording then press the start button.")
        self.wStartButton = QPushButton("Start")

        self.wStack = QStackedWidget()
        self.wStack.setContentsMargins(0, 0, 0, 0)

        lyStack1 = QHBoxLayout()
        lyStack1.addWidget(wInstructions)
        lyStack1.addWidget(self.wStartButton)

        lyStack2 = QHBoxLayout()
        lyStack2.addWidget(self.wBlockCount)
        lyStack2.addWidget(self.wProgressBar)

        wStack1 = QWidget()
        wStack1.setContentsMargins(0, 0, 0, 0)
        lyStack1.setContentsMargins(0, 0, 0, 0)
        wStack1.setLayout(lyStack1)

        wStack2 = QWidget()
        wStack2.setContentsMargins(0, 0, 0, 0)
        lyStack2.setContentsMargins(0, 0, 0, 0)
        wStack2.setLayout(lyStack2)

        self.wStack.addWidget(wStack1)
        self.wStack.addWidget(wStack2)
        self.wStack.setCurrentIndex(0)

        lyStatusLine = QHBoxLayout()
        lyStatusLine.addStretch()
        lyStatusLine.addWidget(self.wStack)
        lyStatusLine.addStretch()

        ly.addWidget(self.wImage)
        ly.addLayout(lyStatusLine)
        ly.setStretchFactor(self.wImage, 1)
        ly.setStretchFactor(lyStatusLine, 0)

        self._nextBlock = 0
        self._data = None

        self.wStartButton.clicked.connect(self.startTransfer)
        self._timer = QTimer()
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._showNextBlock)
        self._blockCount = None
        self._next_qr = None

    @property
    def delay(self):
        return self._timer.interval() / 1000

    @delay.setter
    def delay(self, value):
        self._timer.setInterval(math.ceil(value * 1000))

    @property
    def rate(self):
        return 1 / self.delay

    @rate.setter
    def rate(self, value):
        self.delay = 1 / value

    def max_symbol_size(self):
        print(self.wImage.width(), self.wImage.height())
        return min(self.wImage.width(), self.wImage.height())

    def render(self, packet):
        return packet_image(packet, self.max_symbol_size())

    def header_packet(self):
        if self.data is None:
            raise RuntimeError("no data")

        m = hashlib.sha3_256()
        m.update(self._data)

        return struct.pack(">6sHQH32s",
            encodeindex(HEADER_PACKET_INDEX), # packet index
            2, # protocol version
            len(self._data),  # file size
            PACKET_SIZE,  # packet size
            m.digest()  # sha3-256 of file
        )

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, value):
        self._data = value
        self._blockCount = math.ceil(len(self._data) / BLOCK_SIZE)
        self.wProgressBar.setRange(0, self._blockCount)

        self.wImage.setPixmap(self.render(self.header_packet()))

    def resizeEvent(self, event):
        super().resizeEvent(event)

        if self.data is not None and self._next_qr is None:
            # Not running; redraw header packet
            self.wImage.setPixmap(self.render(self.header_packet()))

    def startTransfer(self):
        if self._data is None:
            raise RuntimeError("Cannot transfer: set .data property first")

        self.wStack.setCurrentIndex(1)
        self._nextBlock = 0
        self._timer.start()
        self._next_qr = self.getNextQrCode()

    def getNextQrCode(self):
        beginChar = self._nextBlock * BLOCK_SIZE
        endChar = min((self._nextBlock + 1) * BLOCK_SIZE, len(self._data))

        block = self._data[beginChar:endChar]
        packet = encodeindex(self._nextBlock) + block

        return self.render(packet)

    def _showNextBlock(self):
        # Symbol is already this size, unless the window size has changed.
        self.wImage.setPixmap(
            self._next_qr.scaled(
                self.max_symbol_size(),
                self.max_symbol_size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation
            )
        )

        self.wProgressBar.setValue(self._nextBlock + 1)
        self.wBlockCount.setText(f"{self._nextBlock+1}/{self._blockCount}")

        self._nextBlock += 1
        if self._nextBlock == self._blockCount:
            self._timer.stop()
            return

        self._next_qr = self.getNextQrCode()


def main():
    app = QApplication([])
    w = SendWindow()

    path = QFileDialog.getOpenFileName(None, "Select a file to transfer", os.getcwd())[0]
    with open(path, "rb") as f:
        data = f.read()
    w.data = data
    w.rate = 15

    w.showMaximized()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
