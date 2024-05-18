import sys

from PySide6.QtWidgets import QApplication

from .interface import SetupWindow


def main():
    app = QApplication([])
    setup = SetupWindow()

    setup.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
