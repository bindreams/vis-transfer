import os
import sys

_dir = os.path.dirname(__file__)
sys.path.insert(0, f"{_dir}/external/pyzbar")

with os.add_dll_directory(f"{_dir}/lib"):
    from pyzbar.pyzbar import *
