import av

from .constants import DatamatrixWidth
from .core import ddm_stream, ddm_stream_header

def generate_video(fd, /, *, output_path, symbol_size=DatamatrixWidth):
    with av.open(output_path, mode="w") as container:
        stream = container.add_stream("vp9", rate=1, options={"lossless": "1"})
        stream.pix_fmt = "gbrp"

        header = ddm_stream_header(fd, symbol_size=symbol_size)
        stream.width = header.size[0]
        stream.height = header.size[1]

        frame = av.VideoFrame.from_image(header)
        for packet in stream.encode(frame):
            container.mux_one(packet)

        for image in ddm_stream(fd, symbol_size=symbol_size):
            frame = av.VideoFrame.from_image(image)
            for packet in stream.encode(frame):
                container.mux_one(packet)

        for packet in stream.encode():
            container.mux_one(packet)
