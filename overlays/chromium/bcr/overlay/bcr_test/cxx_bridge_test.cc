#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <memory>
#include <string>

#include "bcr_test/cxx_bridge.rs.h"
#include "bcr_test/cxx_bridge_types.h"
#include "partition_alloc/partition_alloc.h"

namespace native_test {
std::unique_ptr<std::string> cpp_reverse(rust::Str input) {
  auto value = std::make_unique<std::string>(input.data(), input.size());
  std::reverse(value->begin(), value->end());
  return value;
}
}

int main() {
  partition_alloc::PartitionAllocGlobalInit([](size_t) { std::abort(); });
  const uint64_t values[] = {7, 14, 21};
  if (native_test::rust_sum(rust::Slice<const uint64_t>(values, 3)) != 42) return 1;
  auto result = native_test::roundtrip("Chromium142");
  if (std::string(result.data(), result.size()) != "241muimorhC") return 2;
  if (!native_test::roundtrip("").empty()) return 3;
  auto normalize = [](const char* input, bool lenient) {
    auto json = native_test::normalize_json(input, lenient);
    return std::string(json.data(), json.size());
  };
  const char* input = R"({/* Chromium options */"items":[1,true,null,],"text":"\x41\uD800",})";
  if (normalize(input, true) != "{\"items\":[1,true,null],\"text\":\"A\xEF\xBF\xBD\"}") return 4;
  if (!normalize(input, false).empty()) return 5;
  if (!normalize("{} trailing", true).empty()) return 6;
  if (normalize("[1.2345678901234567,18446744073709551615]", false) !=
      "[1.2345678901234567,18446744073709551615]") return 7;
  if (!normalize("\"\\uD800\"", false).empty()) return 8;
  return 0;
}
