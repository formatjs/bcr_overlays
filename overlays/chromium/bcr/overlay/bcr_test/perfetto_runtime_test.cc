#include <csignal>
#include <cstdint>
#include <map>
#include <memory>
#include <string>
#include <sys/resource.h>
#include <sys/wait.h>
#include <unistd.h>
#include <vector>

#include <json/json.h>
#include <zlib.h>

#include "third_party/perfetto/include/perfetto/tracing.h"
#include "perfetto/tracing/track_event.h"
#include "protos/perfetto/config/track_event/track_event_config.gen.h"
#include "protos/perfetto/trace/interned_data/interned_data.pbzero.h"
#include "protos/perfetto/trace/trace.pbzero.h"
#include "protos/perfetto/trace/trace_packet.pbzero.h"
#include "protos/perfetto/trace/track_event/debug_annotation.pbzero.h"
#include "protos/perfetto/trace/track_event/track_event.pbzero.h"

static_assert(JSON_USE_EXCEPTION == 0);
static_assert(JSON_USE_NULLREF == 0);
static_assert(PERFETTO_BUILDFLAG(PERFETTO_CHROMIUM_BUILD));
static_assert(PERFETTO_DCHECK_IS_ON());

PERFETTO_DEFINE_CATEGORIES(perfetto::Category("native"));
PERFETTO_TRACK_EVENT_STATIC_STORAGE();

bool DependenciesWork() {
  Json::Value original(Json::objectValue);
  original["revision"] = 142;
  original["name"] = "Chromium";
  Json::StreamWriterBuilder writer;
  const auto text = Json::writeString(writer, original);
  Json::Value parsed;
  Json::CharReaderBuilder reader;
  std::string errors;
  if (!std::unique_ptr<Json::CharReader>(reader.newCharReader())->parse(
          text.data(), text.data() + text.size(), &parsed, &errors)) return false;
  if (parsed != original) return false;
  const rlimit no_core = {0, 0};
  if (setrlimit(RLIMIT_CORE, &no_core)) return false;
  const pid_t child = fork();
  if (child < 0) return false;
  if (child == 0) {
    Json::Value invalid("not an integer");
    invalid.asInt();
    _exit(99);
  }
  int status = 0;
  if (waitpid(child, &status, 0) != child || !WIFSIGNALED(status) ||
      WTERMSIG(status) != SIGABRT) return false;

  const std::string input("native\0trace", 12);
  std::vector<unsigned char> compressed(compressBound(input.size()));
  uLongf length = compressed.size();
  if (compress2(compressed.data(), &length,
                reinterpret_cast<const Bytef*>(input.data()), input.size(), 6) != Z_OK) return false;
  std::string output(input.size(), '\0');
  uLongf size = output.size();
  if (uncompress(reinterpret_cast<Bytef*>(output.data()), &size,
                 compressed.data(), length) != Z_OK || output != input) return false;
  return crc32(0, reinterpret_cast<const Bytef*>("123456789"), 9) == 0xcbf43926u;
}

int main() {
  if (!DependenciesWork()) return 1;
  perfetto::TracingInitArgs arguments;
  arguments.backends = perfetto::kInProcessBackend;
  perfetto::Tracing::Initialize(arguments);
  perfetto::TrackEvent::Register();
  perfetto::TraceConfig config;
  config.add_buffers()->set_size_kb(1024);
  auto* data_source = config.add_data_sources()->mutable_config();
  data_source->set_name("track_event");
  perfetto::protos::gen::TrackEventConfig track_config;
  track_config.add_disabled_categories("*");
  track_config.add_enabled_categories("native");
  data_source->set_track_event_config_raw(track_config.SerializeAsString());
  auto session = perfetto::Tracing::NewTrace();
  session->Setup(config);
  session->StartBlocking();
  {
    TRACE_EVENT("native", "BrowserBuildProbe", "revision", 142);
  }
  perfetto::TrackEvent::Flush();
  session->StopBlocking();
  const auto bytes = session->ReadTraceBlocking();
  session.reset();
  perfetto::Tracing::Shutdown();

  std::map<std::pair<uint32_t, uint64_t>, std::string> names;
  bool found = false;
  perfetto::protos::pbzero::Trace::Decoder trace(reinterpret_cast<const uint8_t*>(bytes.data()), bytes.size());
  for (auto item = trace.packet(); item; ++item) {
    perfetto::protos::pbzero::TracePacket::Decoder packet(*item);
    const auto sequence = packet.trusted_packet_sequence_id();
    if (packet.has_interned_data()) {
      perfetto::protos::pbzero::InternedData::Decoder data(packet.interned_data());
      for (auto entry = data.event_names(); entry; ++entry) {
        perfetto::protos::pbzero::EventName::Decoder name(*entry);
        names[{sequence, name.iid()}] = name.name().ToStdString();
      }
    }
    if (!packet.has_track_event()) continue;
    perfetto::protos::pbzero::TrackEvent::Decoder event(packet.track_event());
    const auto name = event.has_name() ? event.name().ToStdString() : names[{sequence, event.name_iid()}];
    if (name != "BrowserBuildProbe" || event.type() != perfetto::protos::pbzero::TrackEvent::TYPE_SLICE_BEGIN) continue;
    for (auto value = event.debug_annotations(); value; ++value) {
      perfetto::protos::pbzero::DebugAnnotation::Decoder annotation(*value);
      if (annotation.has_int_value() && annotation.int_value() == 142) found = true;
    }
  }
  return found ? 0 : 2;
}
