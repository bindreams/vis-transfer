import sys
import argparse

from PySide6.QtWidgets import QApplication

from .interface import SetupWindow

def cli():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(title="subcommands", dest="subcommand")

    generate_parser = subparsers.add_parser("generate")
    generate_parser.add_argument("input", type=argparse.FileType("rb"))
    generate_parser.add_argument("-o", "--output", required=True)

    return parser


def main():
    args = cli().parse_args()
    if args.subcommand == "generate":
        from .testing import generate_video
        generate_video(args.input, output_path=args.output)
        return

    app = QApplication([])
    setup = SetupWindow()

    setup.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
