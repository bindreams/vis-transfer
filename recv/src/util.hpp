/// Copyright (C) 2023 Andrey Zhukov
///
/// This file is part of the vis-transfer project, distributed under the GNU GPL version 3.
/// For full terms see https://github.com/andreasxp/vis-transfer/blob/master/LICENSE.md.
#pragma once
#include <expected>
#include <string>
#include <string_view>

/// Replace all occurences of a substring with another string.
void replace_all(std::string& str, std::string_view from, std::string_view to) {
	for (size_t i = str.rfind(from); i != str.npos; i = str.rfind(from, i - 1)) {
		str.replace(i, from.size(), to);
		if (i == 0) break;
	}
}

/// Unwrap a std::expected, either returning its value or throwing its exception.
template<typename T>
decltype(auto) unwrap(T&& r) {
	if (r) return *std::forward<T>(r);
	throw std::forward<T>(r).error();
};

template<typename F>
	requires requires(F f) { f(); }
class ScopeGuard {
private:
	F f;
	bool released = false;

public:
	ScopeGuard(const F& f) : f(f) {}
	ScopeGuard(F&& f) : f(f) {}

	void release() { released = true; }

	~ScopeGuard() {
		if (!released) f();
	}
};
