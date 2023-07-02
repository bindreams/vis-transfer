/// Copyright (C) 2023 Andrey Zhukov
///
/// This file is part of the vis-transfer project, distributed under the GNU GPL version 3.
/// For full terms see https://github.com/andreasxp/vis-transfer/blob/master/LICENSE.md.
#pragma once
#include <cryptopp/sha3.h>
#include <llfio/llfio.hpp>

namespace llfio = LLFIO_V2_NAMESPACE;

struct memfile {
	llfio::mapped_file_handle handle;

	memfile(const std::filesystem::path& path, size_t size) {
		using namespace llfio;

		handle = mapped_file({}, path, file_handle::mode::write, file_handle::creation::if_needed).value();
		handle.truncate(size).value();
	}

	void write(size_t offset, std::span<const uint8_t> bytes) {
		handle.write(offset, {{reinterpret_cast<const std::byte*>(bytes.data()), bytes.size()}});
	}

	std::array<uint8_t, 32> sha3_256() const {
		CryptoPP::SHA3_256 hasher;
		hasher.Update(reinterpret_cast<const CryptoPP::byte*>(handle.address()), handle.maximum_extent().value());

		std::array<uint8_t, 32> result;
		hasher.Final(result.data());
		return result;
	}

	void close() { handle.close().value(); }
};
