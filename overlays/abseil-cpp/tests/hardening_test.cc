#include "absl/base/dynamic_annotations.h"
#ifdef ANNOTATE_BENIGN_RACE
#error Chromium must not inherit unprefixed Abseil annotation macros.
#endif

#include <csignal>
#include <cstdint>
#include <sys/resource.h>
#include <sys/wait.h>
#include <unistd.h>

#include "absl/base/options.h"
#include "absl/container/flat_hash_map.h"
#include "absl/container/inlined_vector.h"
#include "absl/debugging/stacktrace.h"
#include "absl/strings/str_format.h"
#include "absl/types/span.h"

static_assert(ABSL_OPTION_HARDENED == 1);

bool Dies(void (*action)()) {
  const auto child = fork();
  if (child < 0) return false;
  if (child == 0) {
    action();
    _exit(99);
  }
  int status = 0;
  if (waitpid(child, &status, 0) != child || !WIFSIGNALED(status)) return false;
  const int signal = WTERMSIG(status);
  return signal == SIGABRT || signal == SIGILL || signal == SIGTRAP;
}

int main() {
  const rlimit no_core = {0, 0};
  if (setrlimit(RLIMIT_CORE, &no_core)) return 1;
  const int values[] = {142};
  absl::Span<const int> span(values);
  if (span.front() != 142) return 2;
  absl::InlinedVector<int, 4> vector = {1, 4, 2};
  absl::flat_hash_map<int, int> map;
  for (int value : vector) map[value]++;
  if (map.size() != 3 || absl::StrFormat("%s %d", "Chromium", 142) != "Chromium 142") return 3;
  if (!Dies([] {
        const int data[] = {1};
        volatile size_t index = 1;
        volatile int value = absl::Span<const int>(data)[index];
        (void)value;
      })) return 4;
  if (!Dies([] {
        absl::InlinedVector<int, 4> empty;
        volatile int value = empty.back();
        (void)value;
      })) return 5;
  void* frames[16];
  if (absl::GetStackTrace(frames, 16, 0) < 1) return 6;
  return 0;
}
