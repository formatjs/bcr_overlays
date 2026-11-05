#include <csignal>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <sys/resource.h>
#include <sys/wait.h>
#include <unistd.h>

#include "partition_alloc/partition_alloc.h"
#include "partition_alloc/partition_root.h"

static_assert(_LIBCPP_HARDENING_MODE == _LIBCPP_HARDENING_MODE_EXTENSIVE);
static_assert(PA_BUILDFLAG(ENABLE_BACKUP_REF_PTR_SUPPORT));
static_assert(PA_BUILDFLAG(ENABLE_DANGLING_RAW_PTR_CHECKS));
static_assert(PA_BUILDFLAG(EXPENSIVE_DCHECKS_ARE_ON));
static_assert(PA_BUILDFLAG(USE_PARTITION_COOKIE));

int main() {
  partition_alloc::PartitionAllocGlobalInit([](size_t) { std::abort(); });
  {
    partition_alloc::PartitionOptions options;
    options.backup_ref_ptr = partition_alloc::PartitionOptions::kEnabled;
    partition_alloc::PartitionRoot root(options);
    auto* memory = static_cast<unsigned char*>(root.Alloc(64, "native-test"));
    if (!memory) return 1;
    std::memset(memory, 0x5a, 64);
    memory = static_cast<unsigned char*>(root.Realloc(memory, 4096, "native-test"));
    if (!memory) return 1;
    for (size_t i = 0; i < 64; ++i) {
      if (memory[i] != 0x5a) return 1;
    }
    root.Free(memory);

    memory = static_cast<unsigned char*>(
        root.Alloc<partition_alloc::AllocFlags::kZeroFill>(128, "zero-test"));
    if (!memory) return 1;
    for (size_t i = 0; i < 128; ++i) {
      if (memory[i] != 0) return 1;
    }
    root.Free(memory);

    void* aligned = root.AlignedAlloc(64, 256);
    if (!aligned || reinterpret_cast<uintptr_t>(aligned) % 64 != 0) return 1;
    root.Free(aligned);

    const pid_t child = fork();
    if (child < 0) return 1;
    if (child == 0) {
      const rlimit no_core = {0, 0};
      setrlimit(RLIMIT_CORE, &no_core);
      auto* victim = static_cast<unsigned char*>(root.Alloc(64, "cookie-test"));
      const size_t usable = root.GetUsableSize(victim);
      // Corrupt trailing cookie; freeing must trigger allocator's check.
      static_cast<volatile unsigned char*>(victim)[usable] ^= 0xff;
      root.Free(victim);
      _exit(0);
    }
    int status = 0;
    if (waitpid(child, &status, 0) != child || !WIFSIGNALED(status)) return 1;
    const int signal = WTERMSIG(status);
    if (signal != SIGTRAP && signal != SIGILL && signal != SIGABRT) return 1;
  }
  partition_alloc::PartitionAllocGlobalUninitForTesting();
  return 0;
}
