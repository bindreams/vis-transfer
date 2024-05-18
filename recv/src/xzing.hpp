/// Copyright (C) 2023-2024 Anna Zhukova
///
/// This file is part of the vis-transfer project, distributed under the GNU GPL version 3.
/// For full terms see https://github.com/bindreams/vis-transfer/blob/master/LICENSE.md
#pragma once
#include <ZXing/BarcodeFormat.h>
#include <ZXing/ReadBarcode.h>
#include "base.hpp"

namespace readers::zxing {

DecodeResult read(GrayscaleImageView const& image) {
	using namespace ZXing;

	ReaderOptions opts;
	opts.setFormats(BarcodeFormat::DataMatrix);

	ImageView zxing_view{
		image.data.data(),
		image.size[0],
		image.size[1],
		ImageFormat::Lum,
		image.strides[1],
		image.strides[0],
	};

	auto read_result = ReadBarcodes(zxing_view, opts);
	if (read_result.size() == 0) return std::unexpected{DecodeError("no symbol detected")};

	std::vector<std::vector<uint8_t>> result;
	for (auto& symbol : read_result) {
		result.push_back(std::move(symbol.bytes()));
	}

	return result;
}

}  // namespace readers::zxing
