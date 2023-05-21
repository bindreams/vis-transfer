# Copyright (C) 2023 Andrey Zhukov
#
# This file is part of the vis-transfer project, distributed under the GNU GPL version 3.
# For full terms see https://github.com/andreasxp/vis-transfer/blob/master/LICENSE.txt.
import hashlib
import json
import sys
import os
import math

from qrcode import QRCode, constants
from PIL import Image
from PIL.ImageQt import ImageQt
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QFileDialog, QVBoxLayout, QWidget, QHBoxLayout, QProgressBar, QPushButton, QStackedWidget
from time import time


def qr20(data):
    data = (data[0*382:1*382], data[1*382:2*382], data[2*382:3*382])

    qrcodes = [None] * 3
    for i in range(3):
        qrcode = QRCode(
            version=20,
            error_correction=constants.ERROR_CORRECT_H,
            box_size=9,
            border=4
        )
        qrcode.add_data(data[i])
        qrcode_image = qrcode.make_image(fill_color="black", back_color="white")

        qrcodes[i] = qrcode_image.convert("L")

    dense_qrcode = Image.merge("RGB", qrcodes)
    return QPixmap(ImageQt(dense_qrcode))

class SendWindow(QWidget):
    blockSize = 382*3 - 10  # -10 for the block index at the beginning

    def __init__(self):
        super().__init__()

        ly = QVBoxLayout()
        self.setLayout(ly)

        self.setContentsMargins(0, 0, 0, 0)
        ly.setContentsMargins(0, 0, 0, 0)

        self.wQrCode = QLabel()
        self.wQrCode.setAlignment(Qt.AlignmentFlag.AlignCenter)

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

        ly.addWidget(self.wQrCode)
        ly.addLayout(lyStatusLine)

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
    def data(self):
        return self._data

    @data.setter
    def data(self, value):
        self._data = value
        self._blockCount = math.ceil(len(self._data) / self.blockSize)
        self.wProgressBar.setRange(0, self._blockCount)

        m = hashlib.sha256()
        m.update(self._data)

        header_block = json.dumps({"len": len(self._data), "sha": m.hexdigest()}).encode("ascii")
        self.wQrCode.setPixmap(qr20(header_block))

    def startTransfer(self):
        if self._data is None:
            raise RuntimeError("Cannot transfer: set .data property first")

        self.wStack.setCurrentIndex(1)
        self._nextBlock = 0
        self._timer.start()
        self._next_qr = self.getNextQrCode()

    def getNextQrCode(self):
        beginChar = self._nextBlock * self.blockSize
        endChar = min((self._nextBlock + 1) * self.blockSize, len(self._data))

        block = self._data[beginChar:endChar]
        packet = f"{self._nextBlock: 10}".encode("ascii") + block

        return qr20(packet)

    def _showNextBlock(self):
        self.wQrCode.setPixmap(self._next_qr)
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
    w.delay = 1/15

    w.showMaximized()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
