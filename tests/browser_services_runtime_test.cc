#include <algorithm>
#include <array>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

#include "base/at_exit.h"
#include "base/command_line.h"
#include "base/files/file_util.h"
#include "base/files/scoped_temp_dir.h"
#include "base/functional/bind.h"
#include "base/metrics/field_trial.h"
#include "base/run_loop.h"
#include "base/task/single_thread_task_executor.h"
#include "base/task/thread_pool.h"
#include "base/task/thread_pool/thread_pool_instance.h"
#include "base/trace_event/trace_config.h"
#include "components/prefs/pref_change_registrar.h"
#include "components/prefs/pref_registry_simple.h"
#include "components/prefs/pref_service.h"
#include "components/prefs/pref_service_factory.h"
#include "components/prefs/value_map_pref_store.h"
#include "components/variations/variations_associated_data.h"
#include "services/metrics/public/cpp/ukm_source.h"
#include "services/metrics/public/cpp/ukm_source_id.h"
#include "services/tracing/public/cpp/perfetto/perfetto_config.h"
#include "services/tracing/public/cpp/perfetto/trace_packet_tokenizer.h"
#include "snappy/snappy.h"
#include "third_party/metrics_proto/ukm/source.pb.h"
#include "third_party/perfetto/include/perfetto/ext/tracing/core/trace_packet.h"
#include "third_party/perfetto/include/perfetto/tracing/core/data_source_config.h"
#include "third_party/perfetto/protos/perfetto/trace/chrome/chrome_trace_packet.pb.h"
#include "third_party/perfetto/protos/perfetto/trace/track_event/track_event.pb.h"

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

int Preferences() {
  base::ScopedTempDir directory;
  CHECK_CASE(directory.CreateUniqueTempDir());
  auto path = directory.GetPath().AppendASCII("Preferences");
  auto runner = base::ThreadPool::CreateSequencedTaskRunner(
      {base::MayBlock(), base::TaskShutdownBehavior::BLOCK_SHUTDOWN});
  auto registry = base::MakeRefCounted<PrefRegistrySimple>();
  registry->RegisterIntegerPref("browser.count", 0);
  registry->RegisterStringPref("browser.label", "default");
  auto managed = base::MakeRefCounted<ValueMapPrefStore>();
  PrefServiceFactory factory;
  factory.set_managed_prefs(managed);
  factory.SetUserPrefsFile(path, runner.get());
  auto prefs = factory.Create(registry);
  CHECK_CASE(prefs->GetInteger("browser.count") == 0);
  int changed = 0;
  {
    PrefChangeRegistrar registrar;
    registrar.Init(prefs.get());
    registrar.Add("browser.count",
                  base::BindRepeating([](int* count) { ++*count; }, &changed));
    prefs->SetInteger("browser.count", 7);
    managed->SetValue("browser.count", base::Value(99), 0);
    CHECK_CASE(prefs->IsManagedPreference("browser.count"));
    CHECK_CASE(prefs->GetInteger("browser.count") == 99);
    prefs->SetInteger("browser.count", 8);
    CHECK_CASE(prefs->GetInteger("browser.count") == 99);
    managed->RemoveValue("browser.count", 0);
    CHECK_CASE(prefs->GetInteger("browser.count") == 8);
    // Masked writes still notify observers.
    CHECK_CASE(changed == 4);
  }
  prefs->SetString("browser.label", "native \xe2\x9c\x93");
  base::RunLoop committed;
  prefs->CommitPendingWrite(committed.QuitClosure());
  committed.Run();
  CHECK_CASE(base::PathExists(path));
  prefs.reset();
  prefs = factory.Create(registry);
  CHECK_CASE(prefs->GetInteger("browser.count") == 8);
  CHECK_CASE(prefs->GetString("browser.label") == "native \xe2\x9c\x93");
  prefs.reset();
  CHECK_CASE(base::WriteFile(path, "{broken"));
  PrefServiceFactory corrupt_factory;
  corrupt_factory.SetUserPrefsFile(path, runner.get());
  PersistentPrefStore::PrefReadError read_error =
      PersistentPrefStore::PREF_READ_ERROR_NONE;
  corrupt_factory.set_read_error_callback(base::BindRepeating(
      [](PersistentPrefStore::PrefReadError* output,
         PersistentPrefStore::PrefReadError error) { *output = error; },
      &read_error));
  auto corrupt = corrupt_factory.Create(registry);
  base::RunLoop().RunUntilIdle();
  CHECK_CASE(read_error == PersistentPrefStore::PREF_READ_ERROR_JSON_PARSE);
  CHECK_CASE(corrupt->GetInteger("browser.count") == 0);
  return 0;
}

int MetricsAndVariations() {
  const std::array<char, 7> literal = {5, 16, 'h', 'e', 'l', 'l', 'o'};
  std::string uncompressed;
  CHECK_CASE(snappy::Uncompress(literal.data(), literal.size(), &uncompressed));
  CHECK_CASE(uncompressed == "hello");
  CHECK_CASE(!snappy::Uncompress(literal.data(), 3, &uncompressed));
  ukm::SourceId id = ukm::AssignNewSourceId();
  ukm::UkmSource source(id, GURL("https://example.test/native"));
  ukm::Source proto;
  source.PopulateProto(&proto);
  CHECK_CASE(proto.id() == id && proto.urls_size() == 1 &&
             proto.urls(0).url() == "https://example.test/native");
  std::string encoded;
  CHECK_CASE(proto.SerializeToString(&encoded));
  ukm::Source decoded;
  CHECK_CASE(decoded.ParseFromString(encoded));
  CHECK_CASE(decoded.id() == id && decoded.urls_size() == 1 &&
             decoded.urls(0).url() == proto.urls(0).url());
  base::Time now = base::Time::FromSecondsSinceUnixEpoch(1000);
  variations::AssociateGoogleVariationIDForTesting(
      variations::GOOGLE_WEB_PROPERTIES_ANY_CONTEXT, "BazelNative", "Enabled",
      31001,
      variations::TimeWindow(now - base::Seconds(10), now + base::Seconds(10)));
  CHECK_CASE(variations::GetGoogleVariationID(
                 variations::GOOGLE_WEB_PROPERTIES_ANY_CONTEXT, "BazelNative",
                 "Enabled", now) == 31001);
  CHECK_CASE(variations::GetGoogleVariationID(
                 variations::GOOGLE_WEB_PROPERTIES_ANY_CONTEXT, "BazelNative",
                 "Enabled", now + base::Seconds(11)) == variations::EMPTY_ID);
  CHECK_CASE(variations::GetGoogleVariationID(
                 variations::GOOGLE_WEB_PROPERTIES_FIRST_PARTY, "BazelNative",
                 "Enabled", now) == variations::EMPTY_ID);
  return 0;
}

int FragmentedTrace() {
  const std::array<std::string, 3> names = {"begin", std::string(350, 'x'),
                                            "end"};
  std::string encoded;
  for (size_t i = 0; i < names.size(); ++i) {
    perfetto::protos::ChromeTracePacket packet;
    packet.set_trusted_packet_sequence_id(101 + i);
    packet.mutable_track_event()->set_name(names[i]);
    std::string payload;
    CHECK_CASE(packet.SerializeToString(&payload));
    perfetto::TracePacket framed;
    framed.AddSlice(payload.data(), payload.size());
    auto [preamble, length] = framed.GetProtoPreamble();
    encoded.append(preamble, length);
    encoded.append(payload);
  }
  tracing::TracePacketTokenizer tokenizer;
  const std::array<size_t, 5> chunks = {1, 2, 7, 127, 5};
  size_t offset = 0, chunk_index = 0, packet_index = 0;
  while (offset < encoded.size()) {
    size_t length = std::min(chunks[chunk_index++ % chunks.size()],
                             encoded.size() - offset);
    auto packets = tokenizer.Parse(
        reinterpret_cast<const uint8_t*>(encoded.data() + offset), length);
    offset += length;
    for (auto& packet : packets) {
      perfetto::protos::ChromeTracePacket decoded;
      CHECK_CASE(decoded.ParseFromString(packet.GetRawBytesForTesting()));
      CHECK_CASE(packet_index < names.size());
      CHECK_CASE(decoded.trusted_packet_sequence_id() == 101 + packet_index);
      CHECK_CASE(decoded.track_event().name() == names[packet_index]);
      ++packet_index;
    }
  }
  CHECK_CASE(packet_index == names.size() && !tokenizer.has_more());
  tracing::TracePacketTokenizer truncated;
  CHECK_CASE(truncated
                 .Parse(reinterpret_cast<const uint8_t*>(encoded.data()),
                        encoded.size() - 1)
                 .size() == 2);
  CHECK_CASE(truncated.has_more());
  CHECK_CASE(truncated
                 .Parse(reinterpret_cast<const uint8_t*>(encoded.data() +
                                                         encoded.size() - 1),
                        1)
                 .size() == 1);
  CHECK_CASE(!truncated.has_more());
  base::trace_event::TraceConfig chrome_config("bazel", "record-until-full");
  auto config = tracing::GetDefaultPerfettoConfig(chrome_config, true);
  CHECK_CASE(!config.buffers().empty() && !config.data_sources().empty());
  bool track_event = false;
  for (const auto& data_source : config.data_sources()) {
    if (data_source.config().name() == "track_event") {
      CHECK_CASE(
          data_source.config().chrome_config().privacy_filtering_enabled());
      track_event = true;
    }
  }
  CHECK_CASE(track_event);
  return 0;
}

int main(int argc, char** argv) {
  base::AtExitManager at_exit;
  base::CommandLine::Init(argc, argv);
  base::SingleThreadTaskExecutor executor;
  base::FieldTrialList trials;
  base::ThreadPoolInstance::CreateAndStartWithDefaultParams("BrowserServices");
  CHECK_CASE(Preferences() == 0);
  CHECK_CASE(MetricsAndVariations() == 0);
  CHECK_CASE(FragmentedTrace() == 0);
  base::ThreadPoolInstance::Get()->Shutdown();
  return 0;
}
