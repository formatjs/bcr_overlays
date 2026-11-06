#include <cstring>
#include <vector>

#include "base/at_exit.h"
#include "mojo/core/embedder/embedder.h"
#include "mojo/public/cpp/system/buffer.h"
#include "mojo/public/cpp/system/message_pipe.h"

int ExercisePipe() {
  mojo::ScopedMessagePipeHandle sender, receiver;
  if (mojo::CreateMessagePipe(nullptr, &sender, &receiver) != MOJO_RESULT_OK)
    return 10;
  auto buffer = mojo::SharedBufferHandle::Create(4096);
  if (!buffer.is_valid()) return 11;
  auto mapping = buffer->Map(4096);
  if (!mapping) return 12;
  constexpr char payload[] = "Chromium IPC \xc3\xa9";
  std::memcpy(mapping.get(), payload, sizeof(payload));
  MojoHandle transferred = buffer.release().value();
  if (mojo::WriteMessageRaw(sender.get(), payload, sizeof(payload), &transferred,
                            1, MOJO_WRITE_MESSAGE_FLAG_NONE) != MOJO_RESULT_OK)
    return 13;
  std::vector<uint8_t> bytes;
  std::vector<mojo::ScopedHandle> handles;
  if (mojo::ReadMessageRaw(receiver.get(), &bytes, &handles,
                           MOJO_READ_MESSAGE_FLAG_NONE) != MOJO_RESULT_OK)
    return 14;
  if (bytes.size() != sizeof(payload) || handles.size() != 1 ||
      std::memcmp(bytes.data(), payload, sizeof(payload)) != 0)
    return 15;
  mojo::ScopedSharedBufferHandle received(
      mojo::SharedBufferHandle(handles[0].release().value()));
  auto received_mapping = received->Map(4096);
  if (!received_mapping ||
      std::memcmp(received_mapping.get(), payload, sizeof(payload)) != 0)
    return 16;
  return 0;
}

int main() {
  base::AtExitManager at_exit;
  mojo::core::Configuration configuration;
  configuration.is_broker_process = true;
  mojo::core::Init(configuration);
  int result = mojo::core::IsMojoIpczEnabled() ? ExercisePipe() : 17;
  mojo::core::ShutDown();
  return result;
}
