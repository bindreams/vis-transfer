/// Copyright (C) 2023 Andrey Zhukov
///
/// This file is part of the vis-transfer project, distributed under the GNU GPL version 3.
/// For full terms see https://github.com/andreasxp/vis-transfer/blob/master/LICENSE.md.
#pragma once
#include <concepts>
#include <span>
#include <string>
#include "util.hpp"

namespace impl {

template<typename T>
std::string repr(size_t indent, T&& t)
	requires requires {
		{ t.repr() } -> std::convertible_to<std::string>;
	}
{
	std::string result = std::forward<T>(t).repr();
	std::string padding = std::format("{: <{}}", "", indent * 2);

	replace_all(result, "\n", std::format("\n{}", padding));
	result.insert(0, padding);

	return result;
}

std::string repr(size_t indent, std::span<const uint8_t> bytes) {
	(void)indent;

	std::string result(bytes.size() * 2, '\0');
	static constexpr const char* alphabet = "0123456789abcdef";

	for (size_t i = 0; i < bytes.size(); ++i) {
		result[i * 2] = alphabet[bytes[i] / 16];
		result[i * 2 + 1] = alphabet[bytes[i] % 16];
	}

	return result;
}

}  // namespace impl

template<typename T>
std::string repr(T&& val) {
	return impl::repr(0, val);
}

template<typename T>
std::string repr(size_t index, T&& val) {
	return impl::repr(index, val);
}
