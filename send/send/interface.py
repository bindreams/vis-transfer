import itertools
import os
from datetime import timedelta
from pathlib import Path
from queue import Empty as QueueEmpty
from queue import Queue
from threading import Thread

from PIL import Image
from PIL.ImageQt import ImageQt
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from . import constants
from .core import ddm_stream, ddm_stream_header, packet_count


class TransferWindow(QWidget):
    stopped = Signal(bool)
    imageSwitched = Signal(int)

    class GeneratorThread(Thread):
        """A thread that generates new images in background an places them into a queue."""

        ImageBufferSize = 2

        def __init__(self, fd, target_size):
            super().__init__()
            self.fd = fd
            self.target_size = target_size
            self.queue = Queue(maxsize=self.ImageBufferSize or 0)

            self.abort_flag = False

        def run(self):
            def push(index, image):
                image = QPixmap(ImageQt(image.resize((self.target_size, self.target_size), Image.Resampling.NEAREST)))
                self.queue.put((index, image))

            push(constants.HeaderPacketIndex, ddm_stream_header(self.fd, symbol_size=constants.DatamatrixWidth))

            for i, image in zip(itertools.count(), ddm_stream(self.fd, symbol_size=constants.DatamatrixWidth)):
                if self.abort_flag:
                    return
                push(i, image)

            self.queue.put(None)

        def abort(self):
            self.abort_flag = True
            # Discard all items from the queue so that the thread unblocks and notices the abort flag
            try:
                while self.is_alive():
                    self.queue.get_nowait()
            except QueueEmpty:
                pass

            self.join()

    def __init__(self, fd, *, fps=15):
        super().__init__()

        self.fd = fd
        self.target_image_size = self.get_target_size()
        self.packet_count = packet_count(self.fd)

        self.seconds_per_frame = None
        self.fps = fps

        # Layout -------------------------------------------------------------------------------------------------------
        self.setStyleSheet("color: black; background-color:white;")

        ly = QHBoxLayout()
        self.setLayout(ly)

        self.setContentsMargins(0, 0, 0, 0)
        ly.setContentsMargins(0, 0, 0, 0)

        self.wImage = QLabel()
        self.wImage.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.wImage.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Ignored)

        # Control widget -----------------------------------------------------------------------------------------------
        est_time_string = str(timedelta(seconds=round(self.estimated_time)))

        wControlWidgetFrame = QFrame()
        wControlWidgetFrame.setFrameShape(QFrame.Shape.Box)
        wGeneralInfo = QLabel(
            'Begin filming the screen, then press "Start".\n'
            f"Estimated transfer time: {est_time_string}.\n"
            'Press "Abort" at any time to close the window.'
        )
        wGeneralInfo.setWordWrap(True)

        self.wProgressBar = QProgressBar()
        self.wProgressBar.setMinimum(0)
        self.wProgressBar.setMaximum(self.packet_count)
        self.wProgressBar.setTextVisible(False)
        self.wProgressInfo = QLabel(f"-/{self.packet_count}; {est_time_string}")
        self.wStartPauseButton = QPushButton("Start")
        self.wStartPauseButton.clicked.connect(self.start)
        self.wAbortButton = QPushButton("Abort")
        self.wAbortButton.clicked.connect(self.close)
        self.wAbortButton.setStyleSheet("background-color:red;")

        def updateProgress(index):
            self.wProgressBar.setValue(index + 1)

            remaining_time = round((self.packet_count - index - 1) * self.seconds_per_frame)
            remaining_time_string = str(timedelta(seconds=remaining_time))
            self.wProgressInfo.setText(f"{index+1}/{self.packet_count}; {remaining_time_string}")

        self.imageSwitched.connect(updateProgress)

        lyButtonArea = QHBoxLayout()
        lyButtonArea.addWidget(self.wProgressBar)
        lyButtonArea.addWidget(self.wProgressInfo)
        lyButtonArea.addWidget(self.wStartPauseButton)
        lyButtonArea.addWidget(self.wAbortButton)

        lyControlWidgetFrameHolder = QVBoxLayout()
        lyControlWidgetFrame = QVBoxLayout()
        wControlWidgetFrame.setLayout(lyControlWidgetFrame)
        lyControlWidgetFrame.addWidget(wGeneralInfo)
        lyControlWidgetFrame.addLayout(lyButtonArea)
        wControlWidgetFrame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        lyControlWidgetFrameHolder.setContentsMargins(10, 10, 10, 10)
        lyControlWidgetFrameHolder.addWidget(wControlWidgetFrame)
        lyControlWidgetFrameHolder.addStretch()
        # --------------------------------------------------------------------------------------------------------------

        ly.addLayout(lyControlWidgetFrameHolder, 1)
        ly.addWidget(self.wImage, 1, alignment=Qt.AlignCenter)
        ly.addStretch(1)

        # ==============================================================================================================
        self.generator_thread = self.GeneratorThread(self.fd, self.target_image_size)
        self.image_queue = self.generator_thread.queue

        self.generator_thread.start()

        self.timer = QTimer()
        self.timer.timeout.connect(self._switchImage)
        self._switchImage()

    @classmethod
    def screen_size(cls):
        screen_geometry = QApplication.primaryScreen().geometry()
        return (screen_geometry.width(), screen_geometry.height())

    @classmethod
    def get_target_size(cls):
        w, h = cls.screen_size()
        smaller_side = min(w, h)
        return smaller_side - smaller_side % constants.DatamatrixWidth

    @property
    def estimated_time(self):
        assert self.seconds_per_frame is not None
        return self.packet_count * self.seconds_per_frame

    @property
    def fps(self):
        assert self.seconds_per_frame is not None
        return 1 / self.seconds_per_frame

    @fps.setter
    def fps(self, value: float):
        self.seconds_per_frame = 1 / value

    def start(self):
        assert self.seconds_per_frame is not None
        self.timer.setInterval(int(self.seconds_per_frame * 1000))
        self.timer.start()

        self.wStartPauseButton.setEnabled(False)

    def abort(self):
        self.timer.stop()
        self.generator_thread.abort()
        self.stopped.emit(True)
        self.close()

    def _switchImage(self):
        queue_item: tuple[int, QPixmap] | None = self.image_queue.get()
        if queue_item is None:
            self.timer.stop()
            self.generator_thread.join()
            self.close()
            self.stopped.emit(False)
            return

        index, image = queue_item

        self.wImage.setPixmap(image)
        if index != constants.HeaderPacketIndex:
            self.imageSwitched.emit(index)

    def closeEvent(self, event: QCloseEvent):
        self.hide()
        if self.generator_thread.is_alive():
            self.abort()
        event.accept()


class SetupWindow(QWidget):
    def __init__(self):
        super().__init__()

        # Widget layout ================================================================================================
        ly = QVBoxLayout()
        self.setLayout(ly)

        wWelcomeText = QLabel(
            "Welcome to vis-transfer!\n\n"
            'Please select a file or folder you wish to send below. After you press "Proceed", the application will '
            "reopen in fullscreen mode and guide you through the transfer.\n\n"
            'Before you click "Proceed", ensure that you have a phone or a camera to film your computer screen, and, '
            "if necessary, a stand to place the phone on for the duration of the recording. Large files may take a "
            "time to transfer.\n\n"
            "You do not need to film your screen just yet."
        )
        wWelcomeText.setWordWrap(True)

        # File selection -----------------------------------------------------------------------------------------------
        lyFile = QHBoxLayout()
        lyFile.setContentsMargins(0, 0, 0, 0)

        self.wFileSelectButton = QPushButton("Open...")
        self.wFileSelectButton.clicked.connect(self.selectPayload)
        self.wFileSelectButton.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        self.wFileName = QLabel("No file selected")

        lyFile.addWidget(self.wFileSelectButton)
        lyFile.addWidget(self.wFileName)

        # Start button -------------------------------------------------------------------------------------------------
        lyControlArea = QHBoxLayout()
        lyControlArea.setContentsMargins(0, 0, 0, 0)

        self.lyControlButtons = QStackedLayout()
        self.lyControlButtons.setContentsMargins(0, 0, 0, 0)

        self.wStartButton = QPushButton("Proceed")
        self.wStartButton.setDisabled(True)
        self.wStartButton.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        self.wStartButton.clicked.connect(self.beginTransfer)

        self.wStopButton = QPushButton("Abort")
        self.wStopButton.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        self.wStopButton.clicked.connect(self.stopTransfer)

        self.wProgressBar = QProgressBar()
        self.wProgressBar.setTextVisible(False)
        self.wProgressText = QLabel("Missing files")
        self.wProgressText.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)

        self.lyControlButtons.addWidget(self.wStartButton)
        self.lyControlButtons.addWidget(self.wStopButton)

        lyControlArea.addWidget(self.wProgressBar)
        lyControlArea.addWidget(self.wProgressText)
        lyControlArea.addStretch()
        lyControlArea.addLayout(self.lyControlButtons)

        # --------------------------------------------------------------------------------------------------------------
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)

        ly.addWidget(wWelcomeText)
        ly.addLayout(lyFile)
        ly.addSpacing(30)
        ly.addStretch()
        ly.addWidget(separator)

        ly.addLayout(lyControlArea)

        self.setFixedSize(300, 350)

        # ==============================================================================================================
        self.payloadPath = None
        self.wTransferWindow = None
        self.fd = None

    def selectPayload(self):
        path = QFileDialog.getOpenFileName(None, "Select a file to transfer", os.getcwd())[0]

        if path != "":
            self.payloadPath = Path(path)
            self.wFileName.setText(self.payloadPath.name)
            self.wStartButton.setEnabled(True)
            self.wProgressText.setText("Ready")

    def beginTransfer(self):
        assert self.payloadPath is not None
        self.fd = open(self.payloadPath, "rb")

        packet_count_ = packet_count(self.fd)  # No touching fd after TransferWindow has been created!

        self.wTransferWindow = TransferWindow(self.fd)
        self.wTransferWindow.stopped.connect(self.onStopTransfer)

        self.wProgressBar.setMinimum(0)
        self.wProgressBar.setMaximum(packet_count_)

        def updateProgress(i):
            self.wProgressBar.setValue(i + 1)
            self.wProgressText.setText(f"{i+1}/{packet_count_}")

        self.wTransferWindow.imageSwitched.connect(updateProgress)

        self.wTransferWindow.move(0, 0)
        self.wTransferWindow.showFullScreen()

        self.lyControlButtons.setCurrentWidget(self.wStopButton)

    def stopTransfer(self):
        if self.wTransferWindow is not None:
            self.wTransferWindow.abort()

    def onStopTransfer(self, is_aborted):
        self.wTransferWindow = None
        self.fd.close()
        self.lyControlButtons.setCurrentWidget(self.wStartButton)

        if is_aborted:
            self.wProgressText.setText("Aborted")
        else:
            self.wProgressText.setText("Completed")

    def closeEvent(self, event: QCloseEvent):
        if self.wTransferWindow is not None:
            self.wTransferWindow.close()
        return super().closeEvent(event)
