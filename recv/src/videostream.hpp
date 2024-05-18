#pragma once

#include <avcpp/av.h>             // init
#include <avcpp/avutils.h>        // set_logging_level
#include <avcpp/codec.h>          // Codec
#include <avcpp/codeccontext.h>   // VideoDecoderContext
#include <avcpp/formatcontext.h>  // FormatContext
#include <avcpp/packet.h>         // Packet
#include <avcpp/pixelformat.h>    // PixelFormat
#include <avcpp/videorescaler.h>  // VideoRescaler

#include <cstddef>
#include <filesystem>
#include <stdexcept>

struct VideoStream {
private:
	std::filesystem::path path;
	std::size_t stream_index;
	av::Codec codec;

	std::size_t size_ = static_cast<std::size_t>(-1);

public:
	int width;
	int height;
	av::PixelFormat pixel_format;

	struct iterator {
		friend struct VideoStream;

	private:
		av::FormatContext format_ctx;
		av::VideoDecoderContext decoder_ctx;
		std::size_t stream_index = static_cast<std::size_t>(-1);

		av::VideoFrame current_frame = av::VideoFrame::null();

		iterator() = default;
		iterator(VideoStream const& parent) {
			// Open input
			stream_index = parent.stream_index;
			format_ctx.openInput(parent.path.string());
			format_ctx.findStreamInfo();

			decoder_ctx = av::VideoDecoderContext{format_ctx.stream(stream_index), parent.codec};
			decoder_ctx.open();

			// Initialize first value
			++(*this);
		}

	public:
		av::VideoFrame operator*() const { return current_frame; }

		iterator& operator++() {
			while (av::Packet pkt = format_ctx.readPacket()) {
				if (pkt.streamIndex() != stream_index) {
					continue;
				}

				current_frame = decoder_ctx.decode(pkt);
				if (!current_frame) throw std::runtime_error("Encountered an empty frame");

				return *this;
			}

			// example on the website call this code "flush frames". I don't fully understand this.
			current_frame = decoder_ctx.decode(av::Packet{});
			if (current_frame) return *this;

			// no more frames
			current_frame = av::VideoFrame::null();
			return *this;
		}

		friend bool operator==(iterator const& lhs, iterator const& rhs) {
			return lhs.current_frame.pts().timestamp() == rhs.current_frame.pts().timestamp();
		}

		friend bool operator!=(iterator const& lhs, iterator const& rhs) { return !(lhs == rhs); }
	};

	VideoStream(std::filesystem::path path) : path(path) {
		av::init();

		// Open input
		av::FormatContext format_ctx;
		format_ctx.openInput(path.string());

		// Find video stream
		format_ctx.findStreamInfo();
		av::Stream stream;
		for (stream_index = 0; stream_index < format_ctx.streamsCount(); ++stream_index) {
			stream = format_ctx.stream(stream_index);
			if (stream.mediaType() == AVMEDIA_TYPE_VIDEO) {
				break;
			}
		}

		if (stream_index == format_ctx.streamsCount()) {
			throw std::runtime_error("could not find a video stream in the file");
		}

		av::VideoDecoderContext decoder_ctx{stream};
		codec = av::findDecodingCodec(decoder_ctx.raw()->codec_id);

		width = decoder_ctx.width();
		height = decoder_ctx.height();
		pixel_format = decoder_ctx.pixelFormat();
	}

	iterator begin() { return iterator{*this}; }
	iterator end() { return iterator{}; }

	std::size_t size() {
		if (size_ != static_cast<std::size_t>(-1)) return size_;

		av::FormatContext format_ctx;
		format_ctx.openInput(path.string());
		format_ctx.findStreamInfo();

		size_ = 0;
		while (av::Packet pkt = format_ctx.readPacket()) {
			if (pkt.streamIndex() != stream_index) {
				continue;
			}

			++size_;
		}

		return size_;
	}

	static void set_verbose(bool verbose) {
		av::init();
		av::set_logging_level(verbose ? AV_LOG_VERBOSE : AV_LOG_WARNING);
	}
};
