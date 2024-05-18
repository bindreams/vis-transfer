/// Copyright (C) 2023-2024 Anna Zhukova
///
/// This file is part of the vis-transfer project, distributed under the GNU GPL version 3.
/// For full terms see https://github.com/bindreams/vis-transfer/blob/master/LICENSE.md
#pragma once
#include <array>
#include <concepts>
#include <expected>
#include <ranges>
#include <span>
#include <string>
#include "base.hpp"
#include "videostream.hpp"

template<Decoder F>
std::expected<std::vector<uint8_t>, std::pair<int, DecodeError>> read_ddm(av::VideoFrame const& image, F&& decode) {
	using namespace std;

	vector<uint8_t> result(6, 0);  // Allocate 6 bytes for the index
	size_t pixel_count = image.width() * image.height();

	int i = 0;
	for (int ichannel = 0; ichannel < 3; ++ichannel) {
		GrayscaleImageView view{
			.data = span{image.data() + ichannel, pixel_count * 3 - ichannel},  // Offset so R/G/B byte is first
			.size = {image.width(), image.height()},
			.strides = {3, 0},  // Stride over the RGB channels
		};

		DecodeResult decode_result = decode(view);
		if (!decode_result) return unexpected{pair{i, decode_result.error()}};
		auto& symbols = *decode_result;

		if (symbols.size() > 1) return unexpected{pair{i, DecodeError{"more than one symbol detected"}}};

		auto& layer = symbols[0];

		// Write index, which is spliced across all frames
		ranges::copy_n(layer.begin(), 2, result.begin() + (i * 2));

		// Append data (exclude index bytes)
		result.append_range(span{layer}.subspan(2));

		++i;
	}

	return result;
}
