/// Copyright (C) 2023 Andrey Zhukov
///
/// This file is part of the vis-transfer project, distributed under the GNU GPL version 3.
/// For full terms see https://github.com/andreasxp/vis-transfer/blob/master/LICENSE.md.
#pragma once
#include <array>
#include <concepts>
#include <expected>
#include <opencv2/opencv.hpp>
#include <ranges>
#include <span>
#include <string>
#include "base.hpp"

template<Decoder F>
DecodeResult read_dqr(const cv::Mat& image, F&& decode) {
	std::array<cv::Mat, 3> components;
	cv::split(image, components);

	auto& [b, g, r] = components;
	std::vector<uint8_t> result;

	DecodeResult layer = decode(r);
	if (!layer) return layer;
	result = std::move(*layer);

	layer = decode(g);
	if (!layer) return layer;
	result.insert(result.end(), layer->begin(), layer->end());

	layer = decode(b);
	if (!layer) return layer;
	result.insert(result.end(), layer->begin(), layer->end());

	return result;
}
