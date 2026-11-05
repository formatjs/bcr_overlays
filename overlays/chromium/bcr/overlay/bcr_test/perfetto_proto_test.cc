#include <string>

#include "perfetto/protozero/scattered_heap_buffer.h"
#include "protos/perfetto/config/trace_config.gen.h"
#include "protos/perfetto/config/trace_config.pb.h"
#include "protos/perfetto/config/trace_config.pbzero.h"

int main() {
  const std::string expected("\x0a\x02\x08\x40\x18\xe8\x07", 7);
  protozero::HeapBuffered<perfetto::protos::pbzero::TraceConfig> config;
  config->add_buffers()->set_size_kb(64);
  config->set_duration_ms(1000);
  if (config.SerializeAsString() != expected) return 1;

  perfetto::protos::gen::TraceConfig object;
  if (!object.ParseFromArray(expected.data(), expected.size())) return 2;
  if (object.buffers().size() != 1 || object.buffers()[0].size_kb() != 64 ||
      object.duration_ms() != 1000) return 3;
  if (object.SerializeAsString() != expected) return 4;

  perfetto::protos::TraceConfig protobuf;
  if (!protobuf.ParseFromString(expected)) return 5;
  if (protobuf.buffers_size() != 1 || protobuf.buffers(0).size_kb() != 64 ||
      protobuf.duration_ms() != 1000) return 6;
  if (protobuf.SerializeAsString() != expected) return 7;
  return 0;
}
