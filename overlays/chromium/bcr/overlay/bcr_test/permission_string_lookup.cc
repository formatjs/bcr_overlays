#include <charconv>
#include <cstdint>
#include <iostream>
#include <string_view>

#include "third_party/blink/renderer/core/html/html_permission_element_strings_map.h"

int main(int argc, char** argv) {
  if (argc != 3) return 2;
  std::string_view number(argv[2]);
  uint16_t id;
  auto [end, error] = std::from_chars(number.data(), number.data() + number.size(), id);
  if (error != std::errc{} || end != number.data() + number.size()) return 2;
  auto result = blink::GetPermissionElementMessageId(argv[1], id);
  if (result) {
    std::cout << *result;
  } else {
    std::cout << "missing";
  }
}
