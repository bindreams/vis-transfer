/// Copyright (C) 2023 Andrey Zhukov
///
/// This file is part of the vis-transfer project, distributed under the GNU GPL version 3.
/// For full terms see https://github.com/andreasxp/vis-transfer/blob/master/LICENSE.md.
#pragma once
#include <array>
#include <cassert>
#include <concepts>
#include <cstdint>
#include <expected>
#include <ranges>
#include <vector>
#include "base.hpp"
#include "repr.hpp"

template<std::integral T, size_t ByteSize = sizeof(T)>
size_t read(std::span<const uint8_t> bytes, size_t index, T& value) {
	if (index + ByteSize > bytes.size()) throw std::runtime_error("end of data reached");

	value = 0;
	for (size_t i = index; i < index + ByteSize; ++i) {
		if constexpr (ByteSize > 1) value <<= 8;
		value += bytes[i];
	}

	return index + ByteSize;
}

template<std::ranges::sized_range Range>
	requires std::integral<std::ranges::range_value_t<Range>>
size_t read(std::span<const uint8_t> bytes, size_t index, Range& arr) {
	if (index + arr.size() * sizeof(std::ranges::range_value_t<Range>) > bytes.size())
		throw std::runtime_error("end of data reached");

	for (auto& el : arr) {
		index = read(bytes, index, el);
	}

	return index;
}

/**
 * @brief Header packet structure.
 *
 * Header packet is a sequence of bytes in this order:
 * packet index (fixed)    : 6B
 * version                 : 2B
 * file size               : 8B
 * packet size             : 2B
 * sha3-256 hash of file   : 32B
 */
struct StreamHeader {
	static constexpr uint64_t StaticPacketIndex = 0xFFFFFFFFFFFF;
	uint16_t version = 0;
	uint64_t file_size = 0;
	uint16_t packet_size = 0;
	std::array<uint8_t, 32> sha3_256 = {};

	static std::expected<StreamHeader, ParseError> fromBytes(std::span<const uint8_t> bytes) {
		StreamHeader header;
		size_t i = 0;

		uint64_t packet_index = 0;
		i = read<uint64_t, PacketIndexSize>(bytes, i, packet_index);
		if (packet_index != StaticPacketIndex) {
			return std::unexpected<ParseError>(
				std::format("packet index is {} (should be {})", packet_index, StaticPacketIndex)
			);
		}

		i = read(bytes, i, header.version);
		if (header.version != 2) {
			return std::unexpected<ParseError>(std::format("unknown protocol version: {}", header.version));
		}

		i = read(bytes, i, header.file_size);
		i = read(bytes, i, header.packet_size);
		i = read(bytes, i, header.sha3_256);

		return header;
	}

	std::string repr() const {
		return std::format(
			"version: {}\n"
			"file_size: {}\n"
			"packet_size: {}\n"
			"sha3_256: {}",
			version,
			file_size,
			packet_size,
			::repr(sha3_256)
		);
	}
};
