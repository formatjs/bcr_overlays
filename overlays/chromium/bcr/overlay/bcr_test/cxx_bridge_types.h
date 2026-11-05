#ifndef CHROMIUM_BCR_CXX_BRIDGE_TYPES_H_
#define CHROMIUM_BCR_CXX_BRIDGE_TYPES_H_
#include <memory>
#include <string>
#include "rust/cxx.h"
namespace native_test {
std::unique_ptr<std::string> cpp_reverse(rust::Str input);
}
#endif
