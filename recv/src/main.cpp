/// Copyright (C) 2023-2024 Anna Zhukova
///
/// This file is part of the vis-transfer project, distributed under the GNU GPL version 3.
/// For full terms see https://github.com/bindreams/vis-transfer/blob/master/LICENSE.md

#include <fmt/format.h>
#include <CLI/CLI.hpp>
#include <iostream>
#include <stdexcept>
#include <thread>
#include "ddm.hpp"
#include "header.hpp"
#include "memfile.hpp"
#include "queue.hpp"
#include "util.hpp"
#include "videostream.hpp"
#include "xzing.hpp"

namespace ch = std::chrono;

namespace report {

std::string frame(uint64_t iframe, uint64_t nframes) {
	double fraction = double(iframe) / nframes;
	return std::format("frame {}/{} ({:05.2f}%)", iframe, nframes, 100 * fraction);
}

std::string packet(uint64_t ipacket, uint64_t npackets) {
	double fraction = double(ipacket) / npackets;
	return std::format("packet {}/{} ({:05.2f}%)", ipacket, npackets, 100 * fraction);
}

std::string fps(
	uint64_t iframe,
	ch::steady_clock::time_point start_time,
	ch::steady_clock::time_point current_time = ch::steady_clock::now()
) {
	ch::duration<double> time_passed = current_time - start_time;
	double fps = iframe / time_passed.count();

	return std::format("{:.02f} fps", fps);
}

std::string time_remaining(
	uint64_t iframe,
	uint64_t nframes,
	ch::steady_clock::time_point start_time,
	ch::steady_clock::time_point current_time = ch::steady_clock::now()
) {
	double fraction = double(iframe) / nframes;
	ch::duration<double> time_passed = current_time - start_time;

	if (iframe != 0) {
		auto time_remaining = ch::duration_cast<ch::seconds>((time_passed / fraction) - time_passed);
		uint64_t hours = time_remaining.count() / 3600;
		uint64_t minutes = (time_remaining.count() / 60) % 60;
		uint64_t seconds = time_remaining.count() % 60;

		return std::format("{:02}:{:02}:{:02} remaining", hours, minutes, seconds);
	}

	return "--:--:-- remaining";
}

std::string progress(
	ch::steady_clock::time_point start_time,
	uint64_t iframe,
	uint64_t nframes,
	uint64_t ipacket,
	uint64_t npackets
) {
	auto now = ch::steady_clock::now();

	return std::format(
		"{}, {}, {}, {}",
		frame(iframe, nframes),
		packet(ipacket, npackets),
		fps(iframe, start_time, now),
		time_remaining(iframe, nframes, start_time, now)
	);
}

std::string header_progress(ch::steady_clock::time_point start_time, uint64_t iframe, uint64_t nframes) {
	auto now = ch::steady_clock::now();

	return std::format(
		"{}, looking for header, {}, {}",
		frame(iframe, nframes),
		fps(iframe, start_time, now),
		time_remaining(iframe, nframes, start_time, now)
	);
}

}  // namespace report

template<typename E = std::runtime_error, typename... Args>
E except(std::format_string<Args...> fmt, Args&&... args) {
	return E(std::format(fmt, std::forward<Args>(args)...));
};

void receive(const std::filesystem::path& input, const std::filesystem::path& output, int verbosity) {
	auto start_time = ch::steady_clock::now();

	// You can use `combine()` function to chain several read methods. The `combine()` function tries all of the
	// specified methods in order and short-circuits on the first that returns a result.
	// Each method mush satisfy the `Decoder` concept.
	auto read = readers::zxing::read;

	auto log_progress = [verbosity](std::string_view str) {
		if (verbosity > 0) {
			fmt::print("{}\n", str);
		} else {
			fmt::print("\r{}", str);
		}
	};

	// Video reader thread ---------------------------------------------------------------------------------------------
	VideoStream stream{input};
	uint64_t iframe = 0;
	uint64_t nframes = stream.size();

	Queue<av::VideoFrame> frames(1);
	std::jthread reader_thread([&](std::stop_token stop_token) {
		av::VideoRescaler rescaler(  // For converting to RGB
			stream.width,
			stream.height,
			av::PixelFormat(AVPixelFormat::AV_PIX_FMT_RGB24),
			stream.width,
			stream.height,
			stream.pixel_format
		);

		for (auto&& frame : stream) {
			if (stop_token.stop_requested()) break;
			frames.push(rescaler.rescale(frame));
		}
	});

	ScopeGuard join_reader_thread([&] {
		reader_thread.request_stop();
		if (frames.unsafe_size() > 0) frames.pop();  // in case the reader thread is waiting on the queue
	});

	auto read_frame = [&] {
		if (iframe >= nframes) throw std::logic_error("read_frame: reading beyond end of file");

		auto result = frames.pop();
		++iframe;

		return result;
	};

	// Decode process --------------------------------------------------------------------------------------------------
	StreamHeader header;
	while (true) {
		if (iframe >= nframes) throw except("failed to find a header: reached end of file");
		log_progress(report::header_progress(start_time, iframe, nframes));
		av::VideoFrame frame = read_frame();

		auto packet = read_ddm(frame, read);
		if (!packet) {
			if (verbosity >= 1) {
				fmt::print(
					stderr,
					"failed to decode frame at layer {}: {}\n",
					packet.error().first,
					packet.error().second.what()
				);
			}
			continue;
		}
		if (verbosity >= 2) fmt::print(stderr, "contents: {}\n", repr(*packet));

		if (packet_index(*packet) != StreamHeader::StaticPacketIndex) {
			throw except("failed to find a header: found packet {}", packet_index(*packet));
		}

		header = unwrap(StreamHeader::fromBytes(*packet));
		break;
	}

	if (verbosity >= 1) fmt::print(stderr, "found header:\n{}\n", repr(1, header));

	uint64_t metadata_size = PacketIndexSize;
	uint64_t block_size = header.packet_size - metadata_size;
	uint64_t npackets = static_cast<uint64_t>(std::ceil(double(header.file_size) / block_size));
	uint64_t ipacket_next = 0;

	if (verbosity >= 1)
		fmt::print(
			stderr,
			"computed additional info:\n"
			"  metadata_size: {}\n"
			"  block_size: {}\n"
			"  npackets: {}\n",
			metadata_size,
			block_size,
			npackets
		);

	std::filesystem::path output_temp = output;
	output_temp += ".vis-transfer-incomplete";
	ScopeGuard remove_output_temp([&] { std::filesystem::remove(output_temp); });
	memfile mf(output_temp, header.file_size);

	while (iframe < nframes) {
		if (iframe >= nframes) throw except("failed to find packet {}: reached end of file", ipacket_next);
		log_progress(report::progress(start_time, iframe, nframes, ipacket_next, npackets));
		av::VideoFrame frame = read_frame();

		auto packet = read_ddm(frame, read);
		if (!packet) {
			if (verbosity >= 1) {
				fmt::print(
					stderr,
					"failed to decode frame at layer {}: {}\n",
					packet.error().first,
					packet.error().second.what()
				);
			}
			continue;
		}
		if (verbosity >= 2) fmt::print(stderr, "contents: {}\n", repr(*packet));

		uint64_t ipacket = packet_index(*packet);

		if (ipacket < ipacket_next || ipacket == StreamHeader::StaticPacketIndex) {
			if (verbosity >= 1) fmt::print(stderr, "packet already decoded\n");
			continue;
		}
		if (ipacket > ipacket_next) {
			throw except("failed to find packet {}: found packet {} instead", ipacket_next, ipacket);
		}

		uint64_t write_index = ipacket * block_size;
		uint16_t expected_packet_size = ipacket == npackets - 1
											? static_cast<uint16_t>(header.file_size - write_index + metadata_size)
											: header.packet_size;

		if (packet->size() != expected_packet_size) {
			throw except(
				"packet {} corrupted: size is {} instead of expected {}", ipacket, packet->size(), expected_packet_size
			);
		}

		std::span<const uint8_t> block{packet->data() + metadata_size, packet->size() - metadata_size};
		mf.write(write_index, block);
		if (ipacket == npackets - 1) break;
		++ipacket_next;
	}

	if (mf.sha3_256() != header.sha3_256) {
		throw except(
			"file corrupted, hash is incorrect:\nexpected {}\n     got {}", repr(header.sha3_256), repr(mf.sha3_256())
		);
	}

	mf.close();
	log_progress(report::progress(start_time, iframe, nframes, npackets, npackets));
	std::filesystem::rename(output_temp, output);

	if (verbosity == 0) fmt::print("\n");
	fmt::print(stderr, "done\n");
}

int main(int argc, char** argv) {
	CLI::App app{"Visual file transfer decoder.", "vis-recv"};
	app.set_version_flag("-V,--version", "1.0.0");

	std::filesystem::path input;
	std::filesystem::path output;
	bool force = false;
	// clang-format off
	app.add_option("input", input, "Input video recording")
		->required()
		->check(CLI::ExistingFile);
	app.add_option("-o,--output", output, "Output file")
		->required();
	app.add_flag("-f,--force", force, "overwrite output files");
	app.add_flag("-v,--verbose", "enable verbose output");
	// clang-format on

	try {
		argv = app.ensure_utf8(argv);
		app.parse(argc, argv);

		if (!force) {
			auto err = CLI::NonexistentPath(output.string());
			if (!err.empty()) throw CLI::ValidationError{err};
		}

	} catch (const CLI::ParseError& e) {
		return app.exit(e);
	}

	int verbosity = static_cast<int>(app.count("-v"));
	if (verbosity >= 2) VideoStream::set_verbose(true);

	try {
		receive(input, output, verbosity);
	} catch (const std::exception& e) {
		std::cout << "\n" << typeid(e).name() << ": " << e.what() << "\n";
		return 1;
	}
}
