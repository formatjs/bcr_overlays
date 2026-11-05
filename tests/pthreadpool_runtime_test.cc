#include <array>
#include <atomic>
#include <cstdio>
#include <memory>

#include <pthreadpool.h>

#include "base/at_exit.h"
#include "base/command_line.h"
#include "base/task/thread_pool/thread_pool_instance.h"

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

struct Work {
  static constexpr size_t kRows = 137;
  static constexpr size_t kColumns = 173;
  std::array<std::atomic<unsigned>, kRows * kColumns> visits{};
  std::atomic<bool> invalid{false};

  void Reset() {
    for (auto& count : visits)
      count.store(0);
    invalid.store(false);
  }

  static void Element(void* context, size_t i) {
    auto& work = *static_cast<Work*>(context);
    if (i >= work.visits.size()) {
      work.invalid.store(true);
      return;
    }
    work.visits[i].fetch_add(1, std::memory_order_relaxed);
  }

  static void Tile(void* context,
                   size_t row,
                   size_t column,
                   size_t rows,
                   size_t columns) {
    auto& work = *static_cast<Work*>(context);
    if (row >= kRows || column >= kColumns || rows > kRows - row ||
        columns > kColumns - column || rows == 0 || columns == 0) {
      work.invalid.store(true);
      return;
    }
    for (size_t i = row; i < row + rows; ++i) {
      for (size_t j = column; j < column + columns; ++j)
        Element(context, i * kColumns + j);
    }
  }
};

int CheckPool(pthreadpool_t pool) {
  Work work;
  pthreadpool_parallelize_1d(pool, Work::Element, &work, work.visits.size(), 0);
  CHECK_CASE(!work.invalid.load());
  for (const auto& count : work.visits)
    CHECK_CASE(count.load() == 1);

  work.Reset();
  pthreadpool_parallelize_2d_tile_2d(
      pool, Work::Tile, &work, Work::kRows, Work::kColumns, 13, 17,
      PTHREADPOOL_FLAG_DISABLE_DENORMALS | PTHREADPOOL_FLAG_YIELD_WORKERS);
  CHECK_CASE(!work.invalid.load());
  for (const auto& count : work.visits)
    CHECK_CASE(count.load() == 1);

  work.Reset();
  pthreadpool_parallelize_1d(pool, Work::Element, &work, 0, 0);
  CHECK_CASE(!work.invalid.load());
  for (const auto& count : work.visits)
    CHECK_CASE(count.load() == 0);
  return 0;
}

int main(int argc, char** argv) {
  base::AtExitManager at_exit;
  base::CommandLine::Init(argc, argv);
  base::ThreadPoolInstance::CreateAndStartWithDefaultParams("ML");
  CHECK_CASE(CheckPool(nullptr) == 0);
  for (size_t threads : {1, 4, 0}) {
    std::unique_ptr<pthreadpool, decltype(&pthreadpool_destroy)> pool(
        pthreadpool_create(threads), pthreadpool_destroy);
    CHECK_CASE(pool != nullptr);
    CHECK_CASE(pthreadpool_get_threads_count(pool.get()) > 0);
    CHECK_CASE(CheckPool(pool.get()) == 0);
  }
  base::ThreadPoolInstance::Get()->Shutdown();
  std::puts(
      "Chromium pthreadpool: serial, PostJob, tiled, empty 1D ranges passed");
  return 0;
}
