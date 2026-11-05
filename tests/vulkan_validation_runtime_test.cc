#include <dlfcn.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <memory>
#include <string>
#include <vector>

#include "json/json.h"
#include "rules_cc/cc/runfiles/runfiles.h"
#include "vulkan/vk_layer.h"
#include "vulkan/vulkan.h"

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

int main(int argc, char** argv) {
  CHECK_CASE(argc == 3);
  std::string error;
  std::unique_ptr<rules_cc::cc::runfiles::Runfiles> runfiles(
      rules_cc::cc::runfiles::Runfiles::CreateForTest(&error));
  CHECK_CASE(runfiles);
  const std::filesystem::path library(runfiles->Rlocation(argv[1]));
  const std::filesystem::path manifest(runfiles->Rlocation(argv[2]));
  Json::Value document;
  Json::CharReaderBuilder reader;
  std::ifstream input(manifest);
  CHECK_CASE(Json::parseFromStream(reader, input, &document, &error));
  const auto& metadata = document["layer"];
  CHECK_CASE(metadata["name"].asString() == "VK_LAYER_KHRONOS_validation");
  CHECK_CASE(metadata["api_version"].asString() == "1.4.328");
  const auto resolved =
      manifest.parent_path() / metadata["library_path"].asString();
  std::error_code filesystem_error;
  CHECK_CASE(std::filesystem::equivalent(library, resolved, filesystem_error));
  CHECK_CASE(!filesystem_error);

  std::unique_ptr<void, decltype(&dlclose)> layer(
      dlopen(library.c_str(), RTLD_NOW | RTLD_LOCAL), &dlclose);
  if (!layer) {
    std::fprintf(stderr, "%s\n", dlerror());
  }
  CHECK_CASE(layer);
  auto negotiate = reinterpret_cast<PFN_vkNegotiateLoaderLayerInterfaceVersion>(
      dlsym(layer.get(), "vkNegotiateLoaderLayerInterfaceVersion"));
  CHECK_CASE(negotiate);
  VkNegotiateLayerInterface interface{};
  interface.sType = LAYER_NEGOTIATE_INTERFACE_STRUCT;
  interface.loaderLayerInterfaceVersion =
      CURRENT_LOADER_LAYER_INTERFACE_VERSION;
  CHECK_CASE(negotiate(&interface) == VK_SUCCESS);
  CHECK_CASE(interface.loaderLayerInterfaceVersion >= 1);
  CHECK_CASE(interface.pfnGetInstanceProcAddr &&
             interface.pfnGetDeviceProcAddr);
  CHECK_CASE(
      interface.pfnGetInstanceProcAddr(VK_NULL_HANDLE, "vkCreateInstance"));

  const std::string directory = manifest.parent_path().string();
  CHECK_CASE(setenv("VK_LAYER_PATH", directory.c_str(), 1) == 0);
  CHECK_CASE(setenv("VK_LOADER_LAYERS_DISABLE", "~implicit~", 1) == 0);
  unsetenv("VK_ADD_LAYER_PATH");
  unsetenv("VK_INSTANCE_LAYERS");
  unsetenv("VK_LOADER_LAYERS_ENABLE");
  uint32_t count = 0;
  CHECK_CASE(vkEnumerateInstanceLayerProperties(&count, nullptr) == VK_SUCCESS);
  CHECK_CASE(count > 0);
  std::vector<VkLayerProperties> properties(count);
  CHECK_CASE(vkEnumerateInstanceLayerProperties(&count, properties.data()) ==
             VK_SUCCESS);
  bool found = false;
  for (const auto& property : properties) {
    if (std::strcmp(property.layerName, "VK_LAYER_KHRONOS_validation") == 0) {
      CHECK_CASE(property.specVersion == VK_MAKE_API_VERSION(0, 1, 4, 328));
      CHECK_CASE(property.implementationVersion == 1);
      found = true;
    }
  }
  CHECK_CASE(found);
  count = 0;
  CHECK_CASE(vkEnumerateInstanceExtensionProperties(
                 "VK_LAYER_KHRONOS_validation", &count, nullptr) == VK_SUCCESS);
  CHECK_CASE(count > 0);
  std::vector<VkExtensionProperties> extensions(count);
  CHECK_CASE(vkEnumerateInstanceExtensionProperties(
                 "VK_LAYER_KHRONOS_validation", &count, extensions.data()) ==
             VK_SUCCESS);
  found = false;
  for (const auto& extension : extensions) {
    found |= std::strcmp(extension.extensionName,
                         VK_EXT_DEBUG_UTILS_EXTENSION_NAME) == 0;
  }
  CHECK_CASE(found);
  CHECK_CASE(vkEnumerateInstanceExtensionProperties("VK_LAYER_bazel_missing",
                                                    &count, nullptr) ==
             VK_ERROR_LAYER_NOT_PRESENT);
  return 0;
}
