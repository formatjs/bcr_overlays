#include <array>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string_view>

#include "base/at_exit.h"
#include "base/command_line.h"
#include "gpu/command_buffer/client/gles2_cmd_helper.h"
#include "gpu/command_buffer/common/buffer.h"
#include "gpu/command_buffer/service/async_api_interface.h"
#include "gpu/command_buffer/service/command_buffer_direct.h"
#include "gpu/command_buffer/service/common_decoder.h"

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

class CommonCommands final : public gpu::CommonDecoder,
                             public gpu::AsyncAPIInterface {
 public:
  explicit CommonCommands(gpu::CommandBufferDirect& command_buffer)
      : gpu::CommonDecoder(&command_buffer, command_buffer.service()) {}

  void BeginDecoding() override { ++batches; }
  void EndDecoding() override {}
  std::string_view GetLogPrefix() override { return "NativeCommandBuffer"; }

  gpu::error::Error DoCommands(unsigned int limit,
                               const volatile void* buffer,
                               int count,
                               int* processed) override {
    const auto* entries =
        static_cast<const volatile gpu::CommandBufferEntry*>(buffer);
    *processed = 0;
    while (*processed < count && limit--) {
      const auto& header = entries[*processed].value_header;
      const unsigned size = header.size;
      if (size == 0 || size > static_cast<unsigned>(count - *processed))
        return gpu::error::kInvalidSize;
      const auto error =
          DoCommonCommand(header.command, size - 1, entries + *processed);
      if (error != gpu::error::kNoError)
        return error;
      *processed += size;
    }
    return gpu::error::kNoError;
  }

  unsigned batches = 0;
};

int CheckCommandBuffer() {
  gpu::CommandBufferDirect command_buffer;
  CommonCommands decoder(command_buffer);
  command_buffer.set_handler(&decoder);
  gpu::gles2::GLES2CmdHelper gles2_helper(&command_buffer);
  gpu::CommandBufferHelper& helper = gles2_helper;
  helper.SetAutomaticFlushes(false);
  CHECK_CASE(helper.Initialize(256) == gpu::ContextResult::kSuccess);
  std::array<uint8_t, 32> payload{};
  for (unsigned round = 0; round < 200; ++round) {
    for (size_t i = 0; i < payload.size(); ++i)
      payload[i] = static_cast<uint8_t>(round * 17 + i * 31);
    helper.SetBucketSize(7, payload.size());
    helper.SetBucketDataImmediate(7, 0, payload.data(), payload.size());
    helper.Noop(17);
    const int32_t token = helper.InsertToken();
    helper.WaitForToken(token);
    CHECK_CASE(helper.Finish());
    CHECK_CASE(command_buffer.GetLastState().token == token);
    const auto* bucket = decoder.GetBucket(7);
    CHECK_CASE(bucket && bucket->size() == payload.size());
    CHECK_CASE(std::memcmp(bucket->GetData(0, payload.size()), payload.data(),
                           payload.size()) == 0);
  }
  CHECK_CASE(decoder.batches >= 200);
  int32_t shared_id = -1;
  auto shared = command_buffer.CreateTransferBuffer(1024, &shared_id);
  CHECK_CASE(shared && shared_id >= 0);
  auto* memory = static_cast<uint8_t*>(shared->memory());
  for (unsigned i = 0; i < 1024; ++i)
    memory[i] = static_cast<uint8_t>(i * 19);
  helper.SetBucketSize(23, 1024);
  helper.SetBucketData(23, 13, 200, shared_id, 9);
  CHECK_CASE(helper.Finish());
  const auto* bucket = decoder.GetBucket(23);
  CHECK_CASE(bucket && bucket->size() == 1024);
  CHECK_CASE(std::memcmp(bucket->GetData(13, 200), memory + 9, 200) == 0);
  helper.SetBucketData(23, 13, 200, shared_id, 1020);
  CHECK_CASE(!helper.Finish());
  CHECK_CASE(command_buffer.GetLastState().error != gpu::error::kNoError);
  CHECK_CASE(std::memcmp(bucket->GetData(13, 200), memory + 9, 200) == 0);
  command_buffer.DestroyTransferBuffer(shared_id);
  helper.FreeRingBuffer();
  command_buffer.set_handler(nullptr);
  return 0;
}

int main(int argc, char** argv) {
  base::AtExitManager at_exit;
  base::CommandLine::Init(argc, argv);
  CHECK_CASE(CheckCommandBuffer() == 0);
  std::puts(
      "Native GPU command buffer: ring wrap, token fences, buckets, "
      "shared-memory bounds passed");
  return 0;
}
