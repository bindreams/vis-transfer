#pragma once
#include <condition_variable>
#include <cstddef>
#include <deque>
#include <mutex>

/// Simple single-producer, single-consumer queue.
template<typename T>
struct Queue {
private:
	std::vector<T> m_container;
	std::size_t m_maxsize;
	std::size_t m_first = 0;
	std::size_t m_size = 0;

	std::condition_variable m_cv;
	std::mutex m_mutex;

public:
	Queue(std::size_t maxsize) : m_maxsize(maxsize) { m_container.reserve(m_maxsize); }

	void push(T value) {
		std::unique_lock lock{m_mutex};
		m_cv.wait(lock, [&] { return m_size < m_maxsize; });

		std::size_t push_pos = (m_first + m_size) % m_maxsize;
		if (push_pos >= m_container.size()) {
			m_container.push_back(std::move(value));
		} else {
			m_container[push_pos] = std::move(value);
		}
		++m_size;

		lock.unlock();
		m_cv.notify_one();
	}

	T pop() {
		std::unique_lock lock{m_mutex};
		m_cv.wait(lock, [&] { return m_size > 0; });

		T result = std::move(m_container[m_first]);
		m_first = (m_first + 1) % m_maxsize;
		--m_size;

		lock.unlock();
		m_cv.notify_one();
		return result;
	}

	/** Get an inaccurate size of the queue.
	 *
	 * If the reader threads calls this, the size is at least the returned value. If the writer thread calls this, the
	 * size is at most the returned value.
	 */
	std::size_t unsafe_size() { return m_size; }
};
