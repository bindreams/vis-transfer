/// Copyright (C) 2023 Andrey Zhukov
///
/// This file is part of the vis-transfer project, distributed under the GNU GPL version 3.
/// For full terms see https://github.com/andreasxp/vis-transfer/blob/master/LICENSE.md.
#pragma once
#include <ZXing/BarcodeFormat.h>
#include <ZXing/ReadBarcode.h>
#include "base.hpp"

namespace readers::zxing {
namespace detail {

inline ZXing::ImageView ImageViewFromMat(const cv::Mat& image) {
	using ZXing::ImageFormat;

	auto format = [&] {
		switch (image.channels()) {
			case 1:
				return ImageFormat::Lum;
			case 3:
				return ImageFormat::BGR;
			case 4:
				return ImageFormat::BGRX;
			default:
				return ImageFormat::None;
		}
	}();

	if (image.depth() != CV_8U || format == ImageFormat::None)
		throw std::runtime_error("cannot convert opencv image to zxing format");

	return {image.data, image.cols, image.rows, format};
}

}  // namespace detail

DecodeResult read(const cv::Mat& image) {
	using detail::ImageViewFromMat;

	ZXing::DecodeHints hints;
	hints.setFormats(ZXing::BarcodeFormat::DataMatrix);

	auto read_result = ZXing::ReadBarcodes(ImageViewFromMat(image), hints);
	if (read_result.size() == 0) return std::unexpected{DecodeError("no symbol detected")};

	std::vector<std::vector<uint8_t>> result;
	for (auto& symbol : read_result) {
		result.push_back(std::move(symbol.bytes()));
	}

	return result;
}

DecodeResult read_blur3(cv::Mat image) {
	cv::GaussianBlur(image, image, {3, 3}, 0);
	return read(image);
}

}  // namespace readers::zxing
