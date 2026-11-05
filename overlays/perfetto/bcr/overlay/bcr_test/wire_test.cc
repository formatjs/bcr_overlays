#include <string>
#include "perfetto/base/build_config.h"

#ifdef EXPECT_CHROMIUM_CONFIG
static_assert(PERFETTO_BUILDFLAG(PERFETTO_CHROMIUM_BUILD));
static_assert(!PERFETTO_BUILDFLAG(PERFETTO_STANDALONE_BUILD));
static_assert(!PERFETTO_BUILDFLAG(PERFETTO_FORCE_DCHECK_OFF));
#else
static_assert(PERFETTO_BUILDFLAG(PERFETTO_STANDALONE_BUILD));
#endif
static_assert(PERFETTO_BUILDFLAG(PERFETTO_IPC));

#include "fixture.gen.h"
#include "fixture.pbzero.h"
#include "perfetto/protozero/scattered_heap_buffer.h"

int main() {
  const std::string expected("\x08\x8e\x01\x12\x05trace", 10);
  protozero::HeapBuffered<native_test::pbzero::Packet> packet;
  packet->set_timestamp(142);
  packet->set_name("trace");
  if (packet.SerializeAsString() != expected) return 1;
  native_test::gen::Packet object;
  if (!object.ParseFromArray(expected.data(), expected.size())) return 2;
  if (object.timestamp() != 142 || object.name() != "trace") return 3;
  if (object.SerializeAsString() != expected) return 4;
  native_test::pbzero::Packet::Decoder decoder(expected);
  if (decoder.timestamp() != 142 || decoder.name().ToStdString() != "trace") return 5;
  return 0;
}
