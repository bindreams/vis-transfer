/// Copyright (C) 2023-2024 Anna Zhukova
///
/// This file is part of the vis-transfer project, distributed under the GNU GPL version 3.
/// For full terms see https://github.com/bindreams/vis-transfer/blob/master/LICENSE.md
#pragma once
#include <concepts>
#include <expected>
#include <span>
#include <stdexcept>
#include <vector>

struct VisTransferError : std::runtime_error {
	using std::runtime_error::runtime_error;
};

struct DecodeError : VisTransferError {
	using VisTransferError::VisTransferError;
};

struct ParseError : VisTransferError {
	using VisTransferError::VisTransferError;
};

using DecodeResult = std::expected<std::vector<std::vector<std::uint8_t>>, DecodeError>;

struct GrayscaleImageView {
	std::span<std::uint8_t const> data;
	std::array<int, 2> size;
	// pixel-to-pixel, row-to-row, (in bytes). 0 means default.
	std::array<int, 2> strides = {0, 0};
};

template<class F>
concept Decoder = requires(F&& f, GrayscaleImageView const& image) {
	{ f(image) } -> std::same_as<DecodeResult>;
};

/// Combine two instances of Decoder into a single Decoder that tries them in order left-to-right.
template<Decoder F1, Decoder F2>
struct CompoundDecoder {
	F1 f1;
	F2 f2;

	DecodeResult operator()(GrayscaleImageView const& image) {
		DecodeResult r1 = f1(image);
		if (r1) return r1;
		return f2(image);
	}
};

template<Decoder F, Decoder... Fs>
decltype(auto) combine(F&& f, Fs&&... fs) {
	if constexpr (sizeof...(fs) == 0) {
		return f;
	} else {
		return CompoundDecoder<F, decltype(combine(std::forward<Fs>(fs)...))>{f, combine(std::forward<Fs>(fs)...)};
	}
}

constexpr const int PacketIndexSize = 6;
uint64_t packet_index(std::span<const uint8_t> bytes) {
	if (bytes.size() < PacketIndexSize) {
		throw std::runtime_error(std::format("not enough bytes ({}) to read packet index", bytes.size()));
	}

	uint64_t result = 0;
	for (int i = 0; i < 6; ++i) {
		result <<= 8;
		result += bytes[i];
	}

	return result;
}
