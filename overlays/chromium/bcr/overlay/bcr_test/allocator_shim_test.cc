#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <vector>

#include "partition_alloc/partition_address_space.h"
#include "partition_alloc/partition_alloc.h"
#include "partition_alloc/pointers/raw_ptr.h"

bool Managed(const void* pointer) {
  return partition_alloc::IsManagedByPartitionAlloc(
      reinterpret_cast<uintptr_t>(pointer));
}

int main() {
  partition_alloc::PartitionAllocGlobalInit([](size_t) { std::abort(); });
  auto* memory = static_cast<unsigned char*>(std::malloc(64));
  if (!memory || !Managed(memory)) return 1;
  std::memset(memory, 0x5a, 64);
  memory = static_cast<unsigned char*>(std::realloc(memory, 4096));
  if (!memory || !Managed(memory)) return 1;
  for (size_t i = 0; i < 64; ++i) {
    if (memory[i] != 0x5a) return 1;
  }
  std::free(memory);

  auto* object = new int(42);
  if (!Managed(object)) return 1;
  base::raw_ptr<int> tracked = object;
  if (*tracked != 42) return 1;
  tracked = nullptr;
  delete object;

  std::vector<uint64_t> values(256, 0x12345678);
  if (!Managed(values.data()) || values.back() != 0x12345678) return 1;
  return 0;
}
