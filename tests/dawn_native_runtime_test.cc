#include <cstdint>
#include <cstdio>
#include <string>

#include "dawn/dawn_proc.h"
#include "dawn/native/DawnNative.h"
#include "dawn/webgpu_cpp.h"

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

struct ErrorState {
  bool done = false;
  wgpu::PopErrorScopeStatus status = wgpu::PopErrorScopeStatus::Error;
  wgpu::ErrorType type = wgpu::ErrorType::NoError;
  std::string message;
};

void OnError(wgpu::PopErrorScopeStatus status,
             wgpu::ErrorType type,
             wgpu::StringView message,
             ErrorState* state) {
  state->done = true;
  state->status = status;
  state->type = type;
  state->message.assign(message.data, message.length);
}

void Pump(dawn::native::Instance& instance,
          const wgpu::Device& device,
          const bool& done) {
  for (int i = 0; i < 100 && !done; ++i) {
    dawn::native::DeviceTick(device.Get());
    dawn::native::InstanceProcessEvents(instance.Get());
  }
}

int main() {
  dawnProcSetProcs(&dawn::native::GetProcs());
  int unexpected_errors = 0;
  dawn::native::Instance instance;
  wgpu::RequestAdapterOptions options;
  options.backendType = wgpu::BackendType::Null;
  auto adapters = instance.EnumerateAdapters(&options);
  CHECK_CASE(!adapters.empty());
  wgpu::DeviceDescriptor descriptor;
  descriptor.SetUncapturedErrorCallback(
      [](const wgpu::Device&, wgpu::ErrorType, wgpu::StringView, int* count) {
        ++*count;
      },
      &unexpected_errors);
  descriptor.SetDeviceLostCallback(
      wgpu::CallbackMode::AllowProcessEvents,
      [](const wgpu::Device&, wgpu::DeviceLostReason reason, wgpu::StringView,
         int* count) {
        if (reason != wgpu::DeviceLostReason::Destroyed) {
          ++*count;
        }
      },
      &unexpected_errors);
  auto device = wgpu::Device::Acquire(adapters[0].CreateDevice(&descriptor));
  CHECK_CASE(device);

  // Null backend checks native validation and host mappings; no GPU required.
  wgpu::BufferDescriptor buffer_descriptor;
  buffer_descriptor.size = 256;
  buffer_descriptor.usage =
      wgpu::BufferUsage::MapRead | wgpu::BufferUsage::CopyDst;
  buffer_descriptor.mappedAtCreation = true;
  auto buffer = device.CreateBuffer(&buffer_descriptor);
  CHECK_CASE(buffer && buffer.GetSize() == 256);
  auto* bytes = static_cast<uint8_t*>(buffer.GetMappedRange());
  CHECK_CASE(bytes);
  for (size_t i = 0; i < 256; ++i) {
    CHECK_CASE(bytes[i] == 0);
    bytes[i] = static_cast<uint8_t>(i ^ 0x5a);
  }
  buffer.Unmap();
  struct MapState {
    bool done = false;
    wgpu::MapAsyncStatus status = wgpu::MapAsyncStatus::Error;
  } mapped;
  buffer.MapAsync(
      wgpu::MapMode::Read, 0, 256, wgpu::CallbackMode::AllowProcessEvents,
      [](wgpu::MapAsyncStatus status, wgpu::StringView, MapState* state) {
        state->status = status;
        state->done = true;
      },
      &mapped);
  Pump(instance, device, mapped.done);
  CHECK_CASE(mapped.done && mapped.status == wgpu::MapAsyncStatus::Success);
  const auto* read = static_cast<const uint8_t*>(buffer.GetConstMappedRange());
  CHECK_CASE(read);
  for (size_t i = 0; i < 256; ++i) {
    CHECK_CASE(read[i] == static_cast<uint8_t>(i ^ 0x5a));
  }
  buffer.Unmap();

  device.PushErrorScope(wgpu::ErrorFilter::Validation);
  buffer_descriptor.usage =
      wgpu::BufferUsage::MapRead | wgpu::BufferUsage::Storage;
  buffer_descriptor.mappedAtCreation = false;
  auto invalid_buffer = device.CreateBuffer(&buffer_descriptor);
  ErrorState bad_buffer;
  device.PopErrorScope(wgpu::CallbackMode::AllowProcessEvents, OnError,
                       &bad_buffer);
  Pump(instance, device, bad_buffer.done);
  CHECK_CASE(bad_buffer.done &&
             bad_buffer.status == wgpu::PopErrorScopeStatus::Success);
  CHECK_CASE(bad_buffer.type == wgpu::ErrorType::Validation &&
             !bad_buffer.message.empty());

  wgpu::ShaderSourceWGSL wgsl;
  wgsl.code = "@compute @workgroup_size(1) fn main() {}";
  wgpu::ShaderModuleDescriptor module_descriptor;
  module_descriptor.nextInChain = &wgsl;
  auto module = device.CreateShaderModule(&module_descriptor);
  CHECK_CASE(module);
  wgpu::ComputePipelineDescriptor pipeline_descriptor;
  pipeline_descriptor.compute.module = module;
  pipeline_descriptor.compute.entryPoint = "main";
  auto pipeline = device.CreateComputePipeline(&pipeline_descriptor);
  CHECK_CASE(pipeline);
  auto encoder = device.CreateCommandEncoder();
  auto pass = encoder.BeginComputePass();
  pass.SetPipeline(pipeline);
  pass.DispatchWorkgroups(1);
  pass.End();
  auto commands = encoder.Finish();
  device.GetQueue().Submit(1, &commands);

  device.PushErrorScope(wgpu::ErrorFilter::Validation);
  wgsl.code = "@compute @workgroup_size(1) fn main() { let n: i32 = true; }";
  auto invalid_shader = device.CreateShaderModule(&module_descriptor);
  ErrorState bad_shader;
  device.PopErrorScope(wgpu::CallbackMode::AllowProcessEvents, OnError,
                       &bad_shader);
  Pump(instance, device, bad_shader.done);
  CHECK_CASE(bad_shader.done &&
             bad_shader.status == wgpu::PopErrorScopeStatus::Success);
  CHECK_CASE(bad_shader.type == wgpu::ErrorType::Validation &&
             !bad_shader.message.empty());
  CHECK_CASE(unexpected_errors == 0);
  return 0;
}
