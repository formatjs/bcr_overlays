#include <cstdint>
#include <cstdlib>
#include <cstring>

#include "partition_alloc/partition_alloc.h"
#include "partition_alloc/partition_root.h"

int main() {
  partition_alloc::PartitionAllocGlobalInit([](size_t) { std::abort(); });
  {
    partition_alloc::PartitionOptions options;
    options.backup_ref_ptr = partition_alloc::PartitionOptions::kEnabled;
    partition_alloc::PartitionRoot root(options);
    auto* memory = static_cast<unsigned char*>(root.Alloc(64, "cross-smoke"));
    if (!memory) return 1;
    std::memset(memory, 0x5a, 64);
    memory = static_cast<unsigned char*>(root.Realloc(memory, 4096, "cross-smoke"));
    if (!memory) return 1;
    for (size_t i = 0; i < 64; ++i) {
      if (memory[i] != 0x5a) return 1;
    }
    root.Free(memory);
    auto* aligned = root.AlignedAlloc(64, 256);
    if (!aligned || reinterpret_cast<uintptr_t>(aligned) % 64) return 1;
    root.Free(aligned);
  }
  partition_alloc::PartitionAllocGlobalUninitForTesting();
  return 0;
}
