#include <array>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <iterator>
#include <memory>
#include <string>
#include <vector>

#include "rules_cc/cc/runfiles/runfiles.h"
#include "third_party/blink/renderer/platform/fonts/opentype/format_check.rs.h"

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

int main(int argc, char** argv) {
  CHECK_CASE(argc == 4);
  std::string error;
  std::unique_ptr<rules_cc::cc::runfiles::Runfiles> runfiles(
      rules_cc::cc::runfiles::Runfiles::CreateForTest(&error));
  CHECK_CASE(runfiles);
  for (int fixture = 1; fixture <= 3; ++fixture) {
    std::ifstream input(runfiles->Rlocation(argv[fixture]), std::ios::binary);
    CHECK_CASE(input.good());
    std::vector<uint8_t> bytes(std::istreambuf_iterator<char>(input), {});
    CHECK_CASE(!bytes.empty());
    auto info = font_format_check::get_font_format_info(
        rust::Slice<const uint8_t>(bytes.data(), bytes.size()));
    CHECK_CASE(font_format_check::is_colrv0(*info) == (fixture == 2));
    CHECK_CASE(font_format_check::is_colrv1(*info) == (fixture == 3));
    for (size_t length : {0u, 1u, 4u, 11u}) {
      auto truncated = font_format_check::get_font_format_info(
          rust::Slice<const uint8_t>(bytes.data(), length));
      CHECK_CASE(!font_format_check::is_colrv0(*truncated));
      CHECK_CASE(!font_format_check::is_colrv1(*truncated));
      CHECK_CASE(!font_format_check::is_variable(*truncated));
      CHECK_CASE(!font_format_check::is_sbix(*truncated));
      CHECK_CASE(!font_format_check::is_cbdt_cblc(*truncated));
      CHECK_CASE(!font_format_check::is_cff2(*truncated));
      CHECK_CASE(!font_format_check::is_avar2(*truncated));
    }
  }
  const std::array<uint8_t, 16> malformed = {
      't', 't', 'c', 'f', 0, 1, 0, 0, 0xff, 0xff, 0xff, 0xff, 0, 0, 0, 0};
  auto invalid = font_format_check::get_font_format_info(
      rust::Slice<const uint8_t>(malformed.data(), malformed.size()));
  CHECK_CASE(!font_format_check::is_colrv0(*invalid));
  CHECK_CASE(!font_format_check::is_colrv1(*invalid));
  CHECK_CASE(!font_format_check::is_variable(*invalid));
  std::puts(
      "Blink native Rust/CXX: static/COLRv0/COLRv1 fonts, truncation and "
      "malformed TTC rejection passed");
  return 0;
}
