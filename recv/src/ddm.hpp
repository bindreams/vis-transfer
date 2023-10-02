/// Copyright (C) 2023 Andrey Zhukov
///
/// This file is part of the vis-transfer project, distributed under the GNU GPL version 3.
/// For full terms see https://github.com/andreasxp/vis-transfer/blob/master/LICENSE.md.
#pragma once
#include <array>
#include <cassert>
#include <concepts>
#include <expected>
#include <opencv2/opencv.hpp>
#include <ranges>
#include <span>
#include <string>
#include "base.hpp"

template<Decoder F>
std::expected<std::vector<uint8_t>, std::pair<int, DecodeError>> read_ddm(const cv::Mat& image, F&& decode) {
	using namespace std;

	array<cv::Mat, 3> components;
	cv::split(image, components);

	auto& [b, g, r] = components;
	vector<uint8_t> result(6, 0);  // Allocate 6 bytes for the index

	int i = 0;
	for (auto& component : {r, g, b}) {
		DecodeResult decode_result = decode(component);
		if (!decode_result) return unexpected{pair{i, decode_result.error()}};
		auto& symbols = *decode_result;

		if (symbols.size() > 1) return unexpected{pair{i, DecodeError{"more than one symbol detected"}}};
		assert(symbols.size() > 0 && "at least one symbol on success");

		auto& layer = symbols[0];

		// Write index, which is spliced across all frames
		ranges::copy_n(layer.begin(), 2, result.begin() + (i * 2));

		// Append data (exclude index bytes)
		result.append_range(span{layer}.subspan(2));

		++i;
	}

	return result;
}
