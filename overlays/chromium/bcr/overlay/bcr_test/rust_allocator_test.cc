#include <csignal>
#include <cstdint>
#include <sys/resource.h>
#include <sys/wait.h>
#include <unistd.h>
#include <cstdlib>

#include "partition_alloc/partition_address_space.h"
#include "partition_alloc/partition_alloc.h"

extern "C" unsigned char* rust_allocation_new();
extern "C" void rust_allocation_free(unsigned char*);
extern "C" bool rust_reject_unsupported_alignment();
extern "C" bool rust_vec_roundtrip();
extern "C" void rust_allocation_failure();

int main() {
  partition_alloc::PartitionAllocGlobalInit([](size_t) { std::abort(); });
  auto* pointer = rust_allocation_new();
  if (!pointer || reinterpret_cast<uintptr_t>(pointer) % 64) return 1;
  if (!partition_alloc::IsManagedByPartitionAlloc(
          reinterpret_cast<uintptr_t>(pointer))) return 2;
  for (size_t index = 0; index < 4096; ++index) {
    if (pointer[index] != 0x2a) return 3;
  }
  rust_allocation_free(pointer);
  if (!rust_reject_unsupported_alignment()) return 4;
  if (!rust_vec_roundtrip()) return 5;
  const rlimit no_core = {0, 0};
  if (setrlimit(RLIMIT_CORE, &no_core) != 0) return 6;
  const pid_t child = fork();
  if (child < 0) return 7;
  if (child == 0) {
    rust_allocation_failure();
    _exit(99);
  }
  int status = 0;
  if (waitpid(child, &status, 0) != child || !WIFSIGNALED(status)) return 8;
  if (WTERMSIG(status) != SIGTRAP && WTERMSIG(status) != SIGILL) return 9;
  return 0;
}
