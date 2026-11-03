#include <cstring>
#include "third_party/modp_b64/modp_b64.h"

int main() {
  char encoded[modp_b64_encode_len(3)];
  char decoded[modp_b64_decode_len(4)];
  if (modp_b64_encode(encoded, "foo", 3) != 4 ||
      std::strcmp(encoded, "Zm9v") != 0) {
    return 1;
  }
  return modp_b64_decode(decoded, encoded, 4) == 3 &&
                 std::memcmp(decoded, "foo", 3) == 0
             ? 0
             : 1;
}
