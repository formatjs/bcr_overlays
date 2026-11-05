#include <GLES2/gl2.h>
#include <sys/wait.h>
#include <unistd.h>

#include <array>
#include <cstdio>
#include <cstring>
#include <limits>
#include <utility>

#include "base/at_exit.h"
#include "base/command_line.h"
#include "base/memory/unsafe_shared_memory_region.h"
#include "components/viz/common/resources/shared_image_format.h"
#include "components/viz/common/resources/shared_image_format_utils.h"
#include "gpu/command_buffer/common/buffer.h"
#include "gpu/command_buffer/common/discardable_handle.h"
#include "gpu/command_buffer/common/gles2_cmd_format.h"
#include "gpu/command_buffer/common/gles2_cmd_utils.h"
#include "gpu/command_buffer/common/sync_token.h"
#include "third_party/skia/include/core/SkColorType.h"
#include "ui/gl/gl_enums.h"

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

int Service(scoped_refptr<gpu::Buffer> buffer, int input, int output) {
  gpu::ServiceDiscardableHandle handle(buffer, 0, 7);
  CHECK_CASE(!handle.Delete());
  const auto* command = static_cast<const gpu::gles2::cmds::DrawArrays*>(
      buffer->GetDataAddress(16, sizeof(gpu::gles2::cmds::DrawArrays)));
  CHECK_CASE(command && command->mode == GL_TRIANGLES && command->first == 0 &&
             command->count == 3);
  CHECK_CASE(command->header.command == gpu::gles2::cmds::DrawArrays::kCmdId);
  CHECK_CASE(command->header.size == 4);
  gpu::SyncToken token;
  std::memcpy(token.GetData(), buffer->GetDataAddress(64, sizeof(token)),
              sizeof(token));
  CHECK_CASE(token.HasData() && token.verified_flush() &&
             token.release_count() == (uint64_t{1} << 40));
  handle.Unlock();
  CHECK_CASE(write(output, "U", 1) == 1);
  char message = 0;
  CHECK_CASE(read(input, &message, 1) == 1 && message == 'L');
  CHECK_CASE(!handle.Delete());
  handle.Unlock();
  CHECK_CASE(!handle.Delete());
  handle.Unlock();
  CHECK_CASE(handle.Delete());
  CHECK_CASE(write(output, "D", 1) == 1);
  return 0;
}

int SharedCommandMemory() {
  auto region = base::UnsafeSharedMemoryRegion::Create(4096);
  CHECK_CASE(region.IsValid());
  auto duplicate = region.Duplicate();
  auto client_mapping = region.Map();
  auto service_mapping = duplicate.Map();
  CHECK_CASE(client_mapping.IsValid() && service_mapping.IsValid());
  auto client_buffer = gpu::MakeBufferFromSharedMemory(
      std::move(region), std::move(client_mapping));
  auto service_buffer = gpu::MakeBufferFromSharedMemory(
      std::move(duplicate), std::move(service_mapping));
  CHECK_CASE(client_buffer->memory() != service_buffer->memory());
  CHECK_CASE(client_buffer->backing()->GetGUID() ==
             service_buffer->backing()->GetGUID());
  CHECK_CASE(client_buffer->GetDataAddress(4092, 4));
  CHECK_CASE(!client_buffer->GetDataAddress(4092, 5));
  CHECK_CASE(!client_buffer->GetDataAddress(UINT32_MAX, 2));
  CHECK_CASE(client_buffer->GetRemainingSize(4097) == 0);
  CHECK_CASE(
      gpu::DiscardableHandleBase::ValidateParameters(client_buffer.get(), 0));
  CHECK_CASE(
      !gpu::DiscardableHandleBase::ValidateParameters(client_buffer.get(), 1));
  CHECK_CASE(!gpu::DiscardableHandleBase::ValidateParameters(
      client_buffer.get(), 4096));
  CHECK_CASE(!gpu::DiscardableHandleBase::ValidateParameters(
      client_buffer.get(), UINT32_MAX));
  gpu::ClientDiscardableHandle handle(client_buffer, 0, 7);
  auto* command = static_cast<gpu::gles2::cmds::DrawArrays*>(
      client_buffer->GetDataAddress(16, sizeof(gpu::gles2::cmds::DrawArrays)));
  command->Init(GL_TRIANGLES, 0, 3);
  gpu::SyncToken token(gpu::CommandBufferNamespace::IN_PROCESS,
                       gpu::CommandBufferId::FromUnsafeValue(42),
                       uint64_t{1} << 40);
  token.SetVerifyFlush();
  std::memcpy(client_buffer->GetDataAddress(64, sizeof(token)),
              token.GetConstData(), sizeof(token));
  int to_service[2], to_client[2];
  CHECK_CASE(pipe(to_service) == 0 && pipe(to_client) == 0);
  pid_t child = fork();
  CHECK_CASE(child >= 0);
  if (child == 0) {
    close(to_service[1]);
    close(to_client[0]);
    _exit(Service(service_buffer, to_service[0], to_client[1]));
  }
  close(to_service[0]);
  close(to_client[1]);
  char message = 0;
  CHECK_CASE(read(to_client[0], &message, 1) == 1 && message == 'U');
  CHECK_CASE(handle.Lock() && handle.Lock());
  CHECK_CASE(write(to_service[1], "L", 1) == 1);
  CHECK_CASE(read(to_client[0], &message, 1) == 1 && message == 'D');
  CHECK_CASE(!handle.Lock() && handle.CanBeReUsed());
  close(to_service[1]);
  close(to_client[0]);
  int status = 0;
  CHECK_CASE(waitpid(child, &status, 0) == child);
  CHECK_CASE(WIFEXITED(status) && WEXITSTATUS(status) == 0);
  return 0;
}

int ImageLayouts() {
  uint32_t size = 0, row = 0, stride = 0;
  using Util = gpu::gles2::GLES2Util;
  CHECK_CASE(Util::ComputeImageDataSizes(3, 2, 1, GL_RGB, GL_UNSIGNED_BYTE, 4,
                                         &size, &row, &stride));
  CHECK_CASE(size == 21 && row == 9 && stride == 12);
  CHECK_CASE(!Util::ComputeImageDataSizes(std::numeric_limits<int>::max(), 2, 1,
                                          GL_RGBA, GL_UNSIGNED_BYTE, 4, &size,
                                          &row, &stride));
  gpu::gles2::PixelStoreParams params;
  params.alignment = 8;
  params.row_length = 5;
  params.skip_pixels = 1;
  params.skip_rows = 1;
  uint32_t skip = 0;
  CHECK_CASE(Util::ComputeImageDataSizesES3(2, 2, 1, GL_RGB, GL_UNSIGNED_BYTE,
                                            params, &size, &row, &stride, &skip,
                                            nullptr));
  CHECK_CASE(size == 22 && row == 6 && stride == 16 && skip == 19);
  params.skip_rows = std::numeric_limits<int>::max();
  CHECK_CASE(!Util::ComputeImageDataSizesES3(2, 2, 1, GL_RGB, GL_UNSIGNED_BYTE,
                                             params, &size, nullptr, nullptr,
                                             nullptr, nullptr));
  CHECK_CASE(gl::GLEnums::GetStringError(GL_INVALID_OPERATION) ==
             "GL_INVALID_OPERATION");
  const gfx::Size odd_size(5, 3);
  auto nv12 = viz::MultiPlaneFormat::kNV12;
  CHECK_CASE(nv12.NumberOfPlanes() == 2 &&
             nv12.GetPlaneSize(0, odd_size) == odd_size);
  CHECK_CASE(nv12.GetPlaneSize(1, odd_size) == gfx::Size(3, 2));
  CHECK_CASE(nv12.EstimatedSizeInBytes(odd_size) == 27);
  CHECK_CASE(viz::MultiPlaneFormat::kP010.EstimatedSizeInBytes(odd_size) == 54);
  CHECK_CASE(
      viz::SinglePlaneFormat::kRGBA_8888.EstimatedSizeInBytes(odd_size) == 60);
  const gfx::Size huge(std::numeric_limits<int>::max(),
                       std::numeric_limits<int>::max());
  CHECK_CASE(
      !viz::SinglePlaneFormat::kRGBA_F16.MaybeEstimatedSizeInBytes(huge));
  CHECK_CASE(viz::ToClosestSkColorType(nv12, 0) == kAlpha_8_SkColorType);
  CHECK_CASE(viz::ToClosestSkColorType(nv12, 1) == kR8G8_unorm_SkColorType);
  return 0;
}

int main(int argc, char** argv) {
  base::AtExitManager at_exit;
  base::CommandLine::Init(argc, argv);
  alarm(30);
  CHECK_CASE(SharedCommandMemory() == 0);
  CHECK_CASE(ImageLayouts() == 0);
  return 0;
}
