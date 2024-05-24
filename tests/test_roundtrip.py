from pathlib import Path
import pytest
import platform
import subprocess as sp

thisdir = Path(__file__).parent
datadir = thisdir / "data"
tempdir = thisdir / ".temp"

data_files = list(datadir.glob("*"))

def decode(path, output_path):
    exe = "recv/dist/bin/vis-recv"
    if platform.system() == "Windows":
        exe += ".exe"

    sp.run([exe, str(path), "-fo", str(output_path)], check=True)

def compare(fd1, fd2):
    index = 0

    while True:
        buffer1 = fd1.read(32767)
        buffer2 = fd2.read(32767)

        for b1, b2 in zip(buffer1, buffer2):
            if b1 != b2:
                return index, b1, b2
            index += 1

        if len(buffer1) < len(buffer2):
            return index, None, buffer2[len[buffer1]]
        if len(buffer1) > len(buffer2):
            return index, buffer1[len[buffer2]], None

        if len(buffer1) == 0:  # End of both files
            break

    return None

@pytest.mark.parametrize("path", data_files)
def test_roundrip(path):
    from vis_transfer.testing import generate_video
    tempdir.mkdir(exist_ok=True)

    video_path = tempdir / f"{path.name}.mkv"
    decoded_path = tempdir / f"decoded-{path.name}"

    with open(path, "rb") as fd:
        generate_video(fd, output_path=video_path)

    decode(video_path, decoded_path)

    with open(path, "rb") as fd1, open(decoded_path, "rb") as fd2:
        result = compare(fd1, fd2)
        if result is not None:
            pos, b1, b2 = result

            b1 = hex(b1) if b1 is not None else "<eof>"
            b2 = hex(b2) if b2 is not None else "<eof>"
            pytest.fail(
                f"Roundtrip for {path.name} has failed. Files diverged on byte {pos}:\n"
                f"  original: {b1}\n"
                f"   decoded: {b2}"
            )
