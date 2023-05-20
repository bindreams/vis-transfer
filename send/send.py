# Copyright (C) 2023 Andrey Zhukov
#
# This file is part of the vis-transfer project, distributed under the GNU GPL version 3.
# For full terms see https://github.com/andreasxp/vis-transfer/blob/master/LICENSE.txt.
import base64
import hashlib
import io
import json
import sys
from threading import Thread
import os
from time import sleep
import math

import pyqrcode
from PIL.ImageQt import ImageQt
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QFileDialog, QVBoxLayout, QWidget, QHBoxLayout, QProgressBar


def qr(data):
    qr = pyqrcode.create(
        data, error="H", version=20, mode="binary", encoding="unicode_escape"
    )
    buffer = io.BytesIO()
    qr.png(buffer, scale=9)

    return QPixmap(QImage.fromData(buffer.getvalue()))


def pil_to_qt(img):
    return QPixmap(ImageQt(img))


def generate_qrs(label, data):
    payload = base64.b85encode(data).decode()

    m = hashlib.sha256()
    m.update(data)

    packet0 = json.dumps({"len": len(payload), "sha": m.hexdigest()})
    label.setPixmap(qr(packet0))

    step = 382 - 10
    i = 0
    while i * step < len(payload):
        slice = payload[i * step : min(len(payload), (i + 1) * step)]

        packet = f"{i: 10}" + slice

        label.setPixmap(qr(packet))
        sleep(1)
        i += 1

class SendWindow(QWidget):
    blockSize = 382 - 10  # -10 for the block index at the beginning

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

        lyStatusLine = QHBoxLayout()
        lyStatusLine.addStretch()
        lyStatusLine.addWidget(self.wBlockCount)
        lyStatusLine.addWidget(self.wProgressBar)
        lyStatusLine.addStretch()

        ly.addWidget(self.wQrCode)
        ly.addLayout(lyStatusLine)

        self._nextBlock = 0
        self.data = None

        self._timer = QTimer()
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._showNextBlock)
        self._payload = None
        self._blockCount = None

    @property
    def delay(self):
        return self._timer.interval() / 1000

    @delay.setter
    def delay(self, value):
        self._timer.setInterval(math.ceil(value * 1000))

    def startTransfer(self):
        if self.data is None:
            raise RuntimeError("Cannot transfer: set .data property first")

        self._payload = base64.b85encode(self.data).decode()
        self._blockCount = math.ceil(len(self._payload) / self.blockSize)
        self.wProgressBar.setRange(0, self._blockCount)

        m = hashlib.sha256()
        m.update(self.data)

        header_block = json.dumps({"len": len(self._payload), "sha": m.hexdigest()})
        self.wQrCode.setPixmap(qr(header_block))

        self._nextBlock = 0
        self._timer.start()

    def _showNextBlock(self):
        self._timer.stop()

        beginChar = self._nextBlock * self.blockSize
        endChar = min((self._nextBlock + 1) * self.blockSize, len(self._payload))

        block = self._payload[beginChar:endChar]
        packet = f"{self._nextBlock: 10}" + block

        self.wQrCode.setPixmap(qr(packet))
        self.wProgressBar.setValue(self._nextBlock + 1)
        self.wBlockCount.setText(f"{self._nextBlock+1}/{self._blockCount}")

        self._nextBlock += 1
        if self._nextBlock != self._blockCount:
            self._timer.start()


def main():
    app = QApplication([])
    w = SendWindow()

    path = QFileDialog.getOpenFileName(None, "Select a file to transfer", os.getcwd())[0]
    with open(path, "rb") as f:
        data = f.read()
    w.data = data
    w.delay = 1/15

    QTimer.singleShot(0, w.startTransfer)

    w.showMaximized()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
