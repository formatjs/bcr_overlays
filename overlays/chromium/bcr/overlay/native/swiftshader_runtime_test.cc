#include <dlfcn.h>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <memory>
#include <string>
#include <thread>
#include <vector>

#include "dawn/dawn_proc.h"
#include "dawn/native/DawnNative.h"
#include "dawn/native/VulkanBackend.h"
#include "dawn/webgpu_cpp.h"
#include "json/json.h"
#include "rules_cc/cc/runfiles/runfiles.h"

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

bool HasValidationLayer(const wgpu::Device& device) {
  auto get_proc = reinterpret_cast<PFN_vkGetInstanceProcAddr>(
      dawn::native::vulkan::GetInstanceProcAddr(device.Get(),
                                                "vkGetInstanceProcAddr"));
  if (!get_proc) {
    return false;
  }
  auto enumerate = reinterpret_cast<PFN_vkEnumerateInstanceLayerProperties>(
      get_proc(VK_NULL_HANDLE, "vkEnumerateInstanceLayerProperties"));
  if (!enumerate) {
    return false;
  }
  uint32_t count = 0;
  if (enumerate(&count, nullptr) != VK_SUCCESS || count == 0) {
    return false;
  }
  std::vector<VkLayerProperties> layers(count);
  if (enumerate(&count, layers.data()) != VK_SUCCESS) {
    return false;
  }
  for (const auto& layer : layers) {
    if (std::strcmp(layer.layerName, "VK_LAYER_KHRONOS_validation") == 0) {
      return true;
    }
  }
  return false;
}

int CheckRaster(dawn::native::Instance& instance, const wgpu::Device& device) {
  constexpr uint32_t width = 4, height = 4, row_bytes = 256;
  wgpu::TextureDescriptor texture_descriptor;
  texture_descriptor.size = {width, height, 1};
  texture_descriptor.format = wgpu::TextureFormat::RGBA8Unorm;
  texture_descriptor.usage =
      wgpu::TextureUsage::RenderAttachment | wgpu::TextureUsage::CopySrc;
  auto texture = device.CreateTexture(&texture_descriptor);
  wgpu::ShaderSourceWGSL code;
  code.code = R"(
    @vertex fn vertex_main(@builtin(vertex_index) index: u32) -> @builtin(position) vec4f {
      let positions = array(vec2f(-1, -1), vec2f(3, -1), vec2f(-1, 3));
      return vec4f(positions[index], 0, 1);
    }
    @fragment fn fragment_main() -> @location(0) vec4f {
      return vec4f(0, 1, 0, 1);
    }
  )";
  wgpu::ShaderModuleDescriptor module_descriptor;
  module_descriptor.nextInChain = &code;
  auto module = device.CreateShaderModule(&module_descriptor);
  wgpu::ColorTargetState target;
  target.format = texture_descriptor.format;
  wgpu::FragmentState fragment;
  fragment.module = module;
  fragment.entryPoint = "fragment_main";
  fragment.targetCount = 1;
  fragment.targets = &target;
  wgpu::RenderPipelineDescriptor pipeline_descriptor;
  pipeline_descriptor.vertex.module = module;
  pipeline_descriptor.vertex.entryPoint = "vertex_main";
  pipeline_descriptor.fragment = &fragment;
  auto pipeline = device.CreateRenderPipeline(&pipeline_descriptor);
  CHECK_CASE(pipeline);
  wgpu::BufferDescriptor read_descriptor;
  read_descriptor.size = row_bytes * height;
  read_descriptor.usage =
      wgpu::BufferUsage::CopyDst | wgpu::BufferUsage::MapRead;
  auto readback = device.CreateBuffer(&read_descriptor);
  wgpu::RenderPassColorAttachment color;
  color.view = texture.CreateView();
  color.loadOp = wgpu::LoadOp::Clear;
  color.storeOp = wgpu::StoreOp::Store;
  color.clearValue = {1, 0, 0, 1};
  wgpu::RenderPassDescriptor render_descriptor;
  render_descriptor.colorAttachmentCount = 1;
  render_descriptor.colorAttachments = &color;
  auto encoder = device.CreateCommandEncoder();
  auto pass = encoder.BeginRenderPass(&render_descriptor);
  pass.SetPipeline(pipeline);
  pass.Draw(3);
  pass.End();
  wgpu::TexelCopyTextureInfo source;
  source.texture = texture;
  wgpu::TexelCopyBufferInfo destination;
  destination.buffer = readback;
  destination.layout.bytesPerRow = row_bytes;
  destination.layout.rowsPerImage = height;
  wgpu::Extent3D extent{width, height, 1};
  encoder.CopyTextureToBuffer(&source, &destination, &extent);
  auto commands = encoder.Finish();
  device.GetQueue().Submit(1, &commands);
  struct ReadState {
    bool done = false;
    wgpu::MapAsyncStatus status = wgpu::MapAsyncStatus::Error;
  } state;
  readback.MapAsync(
      wgpu::MapMode::Read, 0, row_bytes * height,
      wgpu::CallbackMode::AllowProcessEvents,
      [](wgpu::MapAsyncStatus status, wgpu::StringView, ReadState* state) {
        state->status = status;
        state->done = true;
      },
      &state);
  const auto deadline =
      std::chrono::steady_clock::now() + std::chrono::seconds(30);
  while (!state.done && std::chrono::steady_clock::now() < deadline) {
    dawn::native::DeviceTick(device.Get());
    dawn::native::InstanceProcessEvents(instance.Get());
    std::this_thread::sleep_for(std::chrono::milliseconds(1));
  }
  CHECK_CASE(state.done && state.status == wgpu::MapAsyncStatus::Success);
  const auto* pixels =
      static_cast<const uint8_t*>(readback.GetConstMappedRange());
  CHECK_CASE(pixels);
  for (uint32_t y = 0; y < height; ++y) {
    for (uint32_t x = 0; x < width; ++x) {
      const auto* pixel = pixels + y * row_bytes + x * 4;
      CHECK_CASE(pixel[0] == 0 && pixel[1] == 255 && pixel[2] == 0 &&
                 pixel[3] == 255);
    }
  }
  readback.Unmap();
  return 0;
}

int main(int argc, char** argv) {
  CHECK_CASE(argc == 4);
  std::string error;
  std::unique_ptr<rules_cc::cc::runfiles::Runfiles> runfiles(
      rules_cc::cc::runfiles::Runfiles::CreateForTest(&error));
  CHECK_CASE(runfiles);
  const std::filesystem::path driver(runfiles->Rlocation(argv[1]));
  const std::filesystem::path layer(runfiles->Rlocation(argv[2]));
  const std::filesystem::path manifest(runfiles->Rlocation(argv[3]));
  Json::Value json;
  {
    std::ifstream file(manifest);
    CHECK_CASE(file.good());
    file >> json;
    CHECK_CASE(!file.fail());
  }
  CHECK_CASE(json["file_format_version"].asString() == "1.0.0");
  CHECK_CASE(json["ICD"]["library_path"].asString() ==
             "./libvk_swiftshader.so");
  CHECK_CASE(std::filesystem::equivalent(
      manifest.parent_path() / json["ICD"]["library_path"].asString(), driver));
  CHECK_CASE(setenv("VK_DRIVER_FILES", manifest.c_str(), 1) == 0);
  const std::string layer_directory =
      (layer.parent_path() / "angledata").string();
  CHECK_CASE(setenv("VK_LAYER_PATH", layer_directory.c_str(), 1) == 0);
  CHECK_CASE(setenv("VK_LOADER_LAYERS_DISABLE", "~implicit~", 1) == 0);
  unsetenv("VK_ADD_DRIVER_FILES");
  unsetenv("VK_INSTANCE_LAYERS");
  unsetenv("VK_LOADER_LAYERS_ENABLE");

  dawnProcSetProcs(&dawn::native::GetProcs());
  std::atomic<int> errors{0};
  const std::string directory = driver.parent_path().string();
  const char* search_paths[] = {directory.c_str()};
  dawn::native::DawnInstanceDescriptor native_descriptor;
  native_descriptor.backendValidationLevel =
      dawn::native::BackendValidationLevel::Full;
  native_descriptor.additionalRuntimeSearchPathsCount = 1;
  native_descriptor.additionalRuntimeSearchPaths = search_paths;
  wgpu::InstanceDescriptor instance_descriptor;
  instance_descriptor.nextInChain = &native_descriptor;
  dawn::native::Instance instance(&instance_descriptor);
  wgpu::RequestAdapterOptions options;
  options.backendType = wgpu::BackendType::Vulkan;
  auto adapters = instance.EnumerateAdapters(&options);
  CHECK_CASE(!adapters.empty());
  wgpu::DeviceDescriptor descriptor;
  descriptor.SetUncapturedErrorCallback(
      [](const wgpu::Device&, wgpu::ErrorType, wgpu::StringView message,
         std::atomic<int>* count) {
        ++*count;
        std::fprintf(stderr, "Dawn error: %.*s\n", int(message.length),
                     message.data);
      },
      &errors);
  descriptor.SetDeviceLostCallback(
      wgpu::CallbackMode::AllowProcessEvents,
      [](const wgpu::Device&, wgpu::DeviceLostReason reason, wgpu::StringView,
         std::atomic<int>* count) {
        if (reason != wgpu::DeviceLostReason::Destroyed) {
          ++*count;
        }
      },
      &errors);
  wgpu::Device device;
  for (auto& native_adapter : adapters) {
    wgpu::Adapter adapter(native_adapter.Get());
    wgpu::AdapterInfo info;
    CHECK_CASE(adapter.GetInfo(&info));
    CHECK_CASE(info.backendType == wgpu::BackendType::Vulkan);
    CHECK_CASE(info.adapterType == wgpu::AdapterType::CPU);
    const std::string description(info.device.data, info.device.length);
    CHECK_CASE(description.find("SwiftShader") != std::string::npos);
    auto candidate =
        wgpu::Device::Acquire(native_adapter.CreateDevice(&descriptor));
    CHECK_CASE(candidate);
    if (HasValidationLayer(candidate)) {
      device = std::move(candidate);
      break;
    }
  }
  CHECK_CASE(device);
  std::unique_ptr<void, decltype(&dlclose)> validation(
      dlopen(layer.c_str(), RTLD_NOW | RTLD_NOLOAD), &dlclose);
  CHECK_CASE(validation);

  constexpr uint32_t count = 32;
  constexpr size_t bytes = count * sizeof(uint32_t);
  wgpu::BufferDescriptor storage_descriptor;
  storage_descriptor.size = bytes;
  storage_descriptor.usage =
      wgpu::BufferUsage::Storage | wgpu::BufferUsage::CopySrc;
  auto storage = device.CreateBuffer(&storage_descriptor);
  wgpu::BufferDescriptor read_descriptor;
  read_descriptor.size = bytes;
  read_descriptor.usage =
      wgpu::BufferUsage::CopyDst | wgpu::BufferUsage::MapRead;
  auto readback = device.CreateBuffer(&read_descriptor);
  wgpu::ShaderSourceWGSL code;
  code.code = R"(
    @group(0) @binding(0) var<storage, read_write> result: array<u32>;
    @compute @workgroup_size(4)
    fn main(@builtin(global_invocation_id) id: vec3<u32>) {
      result[id.x] = id.x * 3u + 7u;
    }
  )";
  wgpu::ShaderModuleDescriptor module_descriptor;
  module_descriptor.nextInChain = &code;
  auto module = device.CreateShaderModule(&module_descriptor);
  wgpu::ComputePipelineDescriptor pipeline_descriptor;
  pipeline_descriptor.compute.module = module;
  pipeline_descriptor.compute.entryPoint = "main";
  auto pipeline = device.CreateComputePipeline(&pipeline_descriptor);
  CHECK_CASE(pipeline);
  wgpu::BindGroupEntry entry;
  entry.binding = 0;
  entry.buffer = storage;
  entry.size = bytes;
  wgpu::BindGroupDescriptor group_descriptor;
  group_descriptor.layout = pipeline.GetBindGroupLayout(0);
  group_descriptor.entryCount = 1;
  group_descriptor.entries = &entry;
  auto group = device.CreateBindGroup(&group_descriptor);
  auto encoder = device.CreateCommandEncoder();
  auto pass = encoder.BeginComputePass();
  pass.SetPipeline(pipeline);
  pass.SetBindGroup(0, group);
  pass.DispatchWorkgroups(count / 4);
  pass.End();
  encoder.CopyBufferToBuffer(storage, 0, readback, 0, bytes);
  auto commands = encoder.Finish();
  device.GetQueue().Submit(1, &commands);
  struct MapState {
    bool done = false;
    wgpu::MapAsyncStatus status = wgpu::MapAsyncStatus::Error;
  } mapped;
  readback.MapAsync(
      wgpu::MapMode::Read, 0, bytes, wgpu::CallbackMode::AllowProcessEvents,
      [](wgpu::MapAsyncStatus status, wgpu::StringView, MapState* state) {
        state->status = status;
        state->done = true;
      },
      &mapped);
  const auto deadline =
      std::chrono::steady_clock::now() + std::chrono::seconds(30);
  while (!mapped.done && std::chrono::steady_clock::now() < deadline) {
    dawn::native::DeviceTick(device.Get());
    dawn::native::InstanceProcessEvents(instance.Get());
    std::this_thread::sleep_for(std::chrono::milliseconds(1));
  }
  CHECK_CASE(mapped.done && mapped.status == wgpu::MapAsyncStatus::Success);
  const auto* values =
      static_cast<const uint32_t*>(readback.GetConstMappedRange());
  CHECK_CASE(values);
  for (uint32_t i = 0; i < count; ++i) {
    CHECK_CASE(values[i] == i * 3u + 7u);
  }
  readback.Unmap();
  CHECK_CASE(CheckRaster(instance, device) == 0);
  CHECK_CASE(errors == 0);
  return 0;
}
