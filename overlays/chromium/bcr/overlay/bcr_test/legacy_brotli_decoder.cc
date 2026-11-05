#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <vector>

#include "brotli/decode.h"

int main(int argc, char** argv) {
  if (argc != 3) return 1;
  char* end = nullptr;
  const auto expected = std::strtoull(argv[2], &end, 10);
  if (!end || *end || expected > 64 * 1024 * 1024) return 2;
  std::ifstream input(argv[1], std::ios::binary);
  if (!input) return 3;
  const std::vector<uint8_t> compressed(
      (std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
  size_t size = expected;
  std::vector<uint8_t> output(size);
  if (BrotliDecoderDecompress(compressed.size(), compressed.data(), &size, output.data()) !=
      BROTLI_DECODER_RESULT_SUCCESS || size != expected) return 4;
  return std::fwrite(output.data(), 1, size, stdout) == size ? 0 : 5;
}
