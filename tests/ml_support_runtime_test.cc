#include <array>
#include <cstdint>
#include <cstdio>
#include <limits>
#include <vector>

#include "cpuinfo.h"
#include "fxdiv.h"
#include "tests/weight_cache_schema_generated.h"

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

int main() {
  CHECK_CASE(cpuinfo_initialize());
  CHECK_CASE(cpuinfo_get_processors_count() > 0);
  CHECK_CASE(cpuinfo_get_cores_count() > 0);
  CHECK_CASE(cpuinfo_get_packages_count() > 0);
  for (uint32_t i = 0; i < cpuinfo_get_processors_count(); ++i) {
    const auto* processor = cpuinfo_get_processor(i);
    CHECK_CASE(processor != nullptr);
    CHECK_CASE(processor->core != nullptr);
    CHECK_CASE(processor->package != nullptr);
  }

  uint64_t random = 0x3d4d51c2d82b14b1ULL;
  for (uint64_t divisor :
       std::array<uint64_t, 12>{1, 2, 3, 7, 16, 31, 257, 65537, 0x100000001ULL,
                                0x7fffffffffffffffULL, 0x8000000000000000ULL,
                                std::numeric_limits<uint64_t>::max()}) {
    const auto prepared = fxdiv_init_uint64_t(divisor);
    for (unsigned i = 0; i < 1024; ++i) {
      random ^= random << 13;
      random ^= random >> 7;
      random ^= random << 17;
      const uint64_t numerator = i == 0 ? 0 : i == 1 ? UINT64_MAX : random;
      const auto result = fxdiv_divide_uint64_t(numerator, prepared);
      CHECK_CASE(result.quotient == numerator / divisor);
      CHECK_CASE(result.remainder == numerator % divisor);
    }
  }

  flatbuffers::FlatBufferBuilder builder;
  namespace cache = tflite::xnnpack::cache::schema;
  const auto buffer = cache::CreateBuffer(builder, 123, 456, 789, 64, 256);
  const auto buffers = builder.CreateVector(
      std::vector<flatbuffers::Offset<cache::Buffer>>{buffer});
  const auto list = cache::CreateBufferList(builder, buffers, 4096);
  cache::FinishBufferListBuffer(builder, list);
  flatbuffers::Verifier verifier(builder.GetBufferPointer(), builder.GetSize());
  CHECK_CASE(cache::VerifyBufferListBuffer(verifier));
  const auto* decoded = cache::GetBufferList(builder.GetBufferPointer());
  CHECK_CASE(decoded->buffers()->size() == 1);
  const auto* entry = decoded->buffers()->Get(0);
  CHECK_CASE(entry->packing_algorithm_id() == 123);
  CHECK_CASE(entry->weights_id() == 456);
  CHECK_CASE(entry->bias_id() == 789);
  CHECK_CASE(decoded->base_offset() + entry->offset() == 4160);
  CHECK_CASE(entry->size() == 256);
  flatbuffers::Verifier truncated(builder.GetBufferPointer(),
                                  builder.GetSize() / 2);
  CHECK_CASE(!cache::VerifyBufferListBuffer(truncated));
  for (unsigned i = 0; i < sizeof(uint32_t); ++i)
    builder.GetBufferPointer()[i] = 0xff;
  flatbuffers::Verifier corrupted(builder.GetBufferPointer(),
                                  builder.GetSize());
  CHECK_CASE(!cache::VerifyBufferListBuffer(corrupted));
  cpuinfo_deinitialize();
  std::puts(
      "BCR CPUinfo topology, FXdiv division, FlatBuffers generation/validation "
      "passed");
  return 0;
}
