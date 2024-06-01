from pathlib import Path
import pytest
import platform
import subprocess as sp

thisdir = Path(__file__).parent
datadir = thisdir / "data"
tempdir = thisdir / ".temp"

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


def assert_file_equivalence(reference_path, actual_path, msg=None):
    with open(reference_path, "rb") as fd1, open(actual_path, "rb") as fd2:
        result = compare(fd1, fd2)
        if result is not None:
            pos, b1, b2 = result

            b1 = hex(b1) if b1 is not None else "<eof>"
            b2 = hex(b2) if b2 is not None else "<eof>"

            if msg != "":
                msg += " "
            pytest.fail(
                f"{msg}Files diverged on byte {pos}:\n"
                f"  reference: {b1}\n"
                f"     actual: {b2}"
            )



@pytest.mark.parametrize("path", (datadir / "encoded").glob("*"))
def test_decode(path):
    video_path = next(path.glob("input.*"))
    decoded_path = tempdir / f"decoded-{path.name}"
    reference_path = next(path.glob("output.*"))

    decode(video_path, decoded_path)
    assert_file_equivalence(reference_path, decoded_path, msg=f"{path.name} was decoded incorrectly.")


@pytest.mark.parametrize("path", (datadir / "roundtrip").glob("*"))
def test_roundrip(path):
    from vis_transfer.testing import generate_video
    tempdir.mkdir(exist_ok=True)

    video_path = tempdir / f"{path.name}.mkv"
    decoded_path = tempdir / f"decoded-{path.name}"

    with open(path, "rb") as fd:
        generate_video(fd, output_path=video_path)

    decode(video_path, decoded_path)
    assert_file_equivalence(path, decoded_path, f"Roundtrip for {path.name} has failed.")
