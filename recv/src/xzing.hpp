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

inline ZXing::Results ReadQRCode(const cv::Mat& image) {
	ZXing::DecodeHints hints;
	hints.setFormats(ZXing::BarcodeFormat::QRCode);

	return ZXing::ReadBarcodes(ImageViewFromMat(image), hints);
}

inline void DrawResult(cv::Mat& img, ZXing::Result res) {
	auto pos = res.position();
	auto zx2cv = [](ZXing::PointI p) { return cv::Point(p.x, p.y); };
	auto contour = std::vector<cv::Point>{zx2cv(pos[0]), zx2cv(pos[1]), zx2cv(pos[2]), zx2cv(pos[3])};
	const auto* pts = contour.data();
	int npts = contour.size();

	cv::polylines(img, &pts, &npts, 1, true, CV_RGB(0, 255, 0));
	cv::putText(img, res.text(), zx2cv(pos[3]) + cv::Point(0, 20), cv::FONT_HERSHEY_DUPLEX, 0.5, CV_RGB(0, 255, 0));
}

}  // namespace detail

DecodeResult read(const cv::Mat& image) {
	using detail::ImageViewFromMat;

	ZXing::DecodeHints hints;
	hints.setFormats(ZXing::BarcodeFormat::QRCode);

	auto read_result = ZXing::ReadBarcodes(ImageViewFromMat(image), hints);
	if (read_result.size() > 1) return std::unexpected{DecodeError("more than one QR code detected")};
	if (read_result.size() == 1) return read_result[0].bytes();

	return std::unexpected{DecodeError("no QR code detected")};
}

DecodeResult read_blur3(cv::Mat image) {
	cv::GaussianBlur(image, image, {3, 3}, 0);
	return read(image);
}

}  // namespace readers::zxing
