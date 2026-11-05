#include <dlfcn.h>
#include <sys/stat.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <string>

#include "dawn/dawn_proc.h"
#include "dawn/native/DawnNative.h"
#include "dawn/webgpu_cpp.h"
#include "rules_cc/cc/runfiles/runfiles.h"
#include "vulkan/vulkan.h"

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

int WriteManifest(const std::string& path, const char* content) {
  FILE* file = std::fopen(path.c_str(), "wb");
  CHECK_CASE(file);
  const bool written = std::fwrite(content, 1, std::strlen(content), file) ==
                       std::strlen(content);
  const bool closed = std::fclose(file) == 0;
  CHECK_CASE(written && closed);
  return 0;
}

int main(int argc, char** argv) {
  CHECK_CASE(argc == 2);
  std::string error;
  std::unique_ptr<rules_cc::cc::runfiles::Runfiles> runfiles(
      rules_cc::cc::runfiles::Runfiles::CreateForTest(&error));
  CHECK_CASE(runfiles);
  const std::string library = runfiles->Rlocation(argv[1]);
  struct stat expected{}, loaded{};
  CHECK_CASE(stat(library.c_str(), &expected) == 0);
  Dl_info info{};
  CHECK_CASE(dladdr(reinterpret_cast<void*>(&vkGetInstanceProcAddr), &info) !=
             0);
  CHECK_CASE(info.dli_fname && stat(info.dli_fname, &loaded) == 0);
  CHECK_CASE(expected.st_dev == loaded.st_dev &&
             expected.st_ino == loaded.st_ino);

  const char* temporary = std::getenv("TEST_TMPDIR");
  CHECK_CASE(temporary);
  const std::string manifest = std::string(temporary) + "/driver.json";
  CHECK_CASE(WriteManifest(manifest, R"({
    "file_format_version": "1.0.0",
    "ICD": {"library_path": "missing-driver.so", "api_version": "1.3.0"}
  })") == 0);
  CHECK_CASE(setenv("VK_DRIVER_FILES", manifest.c_str(), 1) == 0);
  CHECK_CASE(setenv("VK_LAYER_PATH", temporary, 1) == 0);
  CHECK_CASE(setenv("VK_LOADER_LAYERS_DISABLE", "~implicit~", 1) == 0);
  unsetenv("VK_INSTANCE_LAYERS");
  unsetenv("VK_LOADER_LAYERS_ENABLE");
  unsetenv("VK_ADD_DRIVER_FILES");

  uint32_t version = 0;
  CHECK_CASE(vkEnumerateInstanceVersion(&version) == VK_SUCCESS);
  CHECK_CASE(VK_API_VERSION_MAJOR(version) == 1 &&
             VK_API_VERSION_MINOR(version) >= 3);
  CHECK_CASE(vkGetInstanceProcAddr(VK_NULL_HANDLE, "vkCreateInstance") !=
             nullptr);
  CHECK_CASE(vkGetInstanceProcAddr(VK_NULL_HANDLE, "vkInvalidBazelFunction") ==
             nullptr);
  uint32_t extension_count = 0;
  CHECK_CASE(vkEnumerateInstanceExtensionProperties(nullptr, &extension_count,
                                                    nullptr) == VK_SUCCESS);
  VkApplicationInfo application{VK_STRUCTURE_TYPE_APPLICATION_INFO};
  application.pApplicationName = "native-bazel-loader";
  application.apiVersion = VK_API_VERSION_1_1;
  VkInstanceCreateInfo create{VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO};
  create.pApplicationInfo = &application;
  VkInstance instance = VK_NULL_HANDLE;
  CHECK_CASE(vkCreateInstance(&create, nullptr, &instance) ==
             VK_ERROR_INCOMPATIBLE_DRIVER);
  CHECK_CASE(instance == VK_NULL_HANDLE);

  CHECK_CASE(WriteManifest(manifest, "{invalid JSON") == 0);
  CHECK_CASE(vkCreateInstance(&create, nullptr, &instance) ==
             VK_ERROR_INCOMPATIBLE_DRIVER);

  // Exercise the real Dawn Vulkan discovery path with this native loader.
  dawnProcSetProcs(&dawn::native::GetProcs());
  const std::string directory = library.substr(0, library.find_last_of('/'));
  const char* search_paths[] = {directory.c_str()};
  dawn::native::DawnInstanceDescriptor native_descriptor;
  native_descriptor.backendValidationLevel =
      dawn::native::BackendValidationLevel::Full;
  native_descriptor.additionalRuntimeSearchPathsCount = 1;
  native_descriptor.additionalRuntimeSearchPaths = search_paths;
  wgpu::InstanceDescriptor descriptor;
  descriptor.nextInChain = &native_descriptor;
  dawn::native::Instance dawn_instance(&descriptor);
  wgpu::RequestAdapterOptions options;
  options.backendType = wgpu::BackendType::Vulkan;
  CHECK_CASE(dawn_instance.EnumerateAdapters(&options).empty());
  return 0;
}
