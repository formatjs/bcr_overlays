#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <memory>
#include <string>
#include <string_view>
#include <vector>

#include "FLAC/stream_encoder.h"
#include "base/at_exit.h"
#include "base/command_line.h"
#include "base/files/file.h"
#include "base/files/memory_mapped_file.h"
#include "base/files/scoped_temp_dir.h"
#include "base/i18n/icu_util.h"
#include "base/task/thread_pool/thread_pool_instance.h"
#include "leveldb/db.h"
#include "leveldb/env.h"
#include "leveldb/write_batch.h"
#include "media/audio/flac_audio_handler.h"
#include "media/base/audio_bus.h"
#include "media/filters/symphonia_glue.rs.h"
#include "rules_cc/cc/runfiles/runfiles.h"

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

struct EncodedFlac {
  std::vector<uint8_t> file;
  std::vector<std::vector<uint8_t>> packets;
  static FLAC__StreamEncoderWriteStatus Write(const FLAC__StreamEncoder*,
                                              const FLAC__byte* bytes,
                                              size_t count,
                                              uint32_t samples,
                                              uint32_t,
                                              void* opaque) {
    auto& output = *static_cast<EncodedFlac*>(opaque);
    output.file.insert(output.file.end(), bytes, bytes + count);
    if (samples)
      output.packets.emplace_back(bytes, bytes + count);
    return FLAC__STREAM_ENCODER_WRITE_STATUS_OK;
  }
};

int CheckAudio() {
  std::vector<FLAC__int32> input(4099);
  for (size_t i = 0; i < input.size(); ++i)
    input[i] = static_cast<int>(i * 977 % 60001) - 30000;
  input[0] = -32768;
  input[1] = 32767;
  EncodedFlac encoded;
  std::unique_ptr<FLAC__StreamEncoder, decltype(&FLAC__stream_encoder_delete)>
      encoder(FLAC__stream_encoder_new(), FLAC__stream_encoder_delete);
  CHECK_CASE(encoder != nullptr);
  CHECK_CASE(FLAC__stream_encoder_set_channels(encoder.get(), 1));
  CHECK_CASE(FLAC__stream_encoder_set_bits_per_sample(encoder.get(), 16));
  CHECK_CASE(FLAC__stream_encoder_set_sample_rate(encoder.get(), 48000));
  CHECK_CASE(FLAC__stream_encoder_set_compression_level(encoder.get(), 5));
  CHECK_CASE(FLAC__stream_encoder_set_blocksize(encoder.get(), 1024));
  CHECK_CASE(FLAC__stream_encoder_set_total_samples_estimate(encoder.get(),
                                                             input.size()));
  CHECK_CASE(FLAC__stream_encoder_init_stream(
                 encoder.get(), EncodedFlac::Write, nullptr, nullptr, nullptr,
                 &encoded) == FLAC__STREAM_ENCODER_INIT_STATUS_OK);
  CHECK_CASE(FLAC__stream_encoder_process_interleaved(
      encoder.get(), input.data(), input.size()));
  CHECK_CASE(FLAC__stream_encoder_finish(encoder.get()));
  CHECK_CASE(encoded.packets.size() >= 2);
  CHECK_CASE(encoded.file.size() > 42);
  CHECK_CASE(std::memcmp(encoded.file.data(), "fLaC", 4) == 0);
  CHECK_CASE((encoded.file[4] & 0x7f) == 0);
  const unsigned metadata_size =
      (encoded.file[5] << 16) | (encoded.file[6] << 8) | encoded.file[7];
  CHECK_CASE(metadata_size == 34);
  media::SymphoniaDecoderConfig config{};
  config.codec = media::SymphoniaAudioCodec::Flac;
  for (unsigned i = 0; i < metadata_size; ++i)
    config.extra_data.push_back(encoded.file[8 + i]);
  auto decoder = media::init_symphonia_decoder(config);
  CHECK_CASE(decoder.status == media::SymphoniaInitStatus::Ok);
  size_t decoded_frames = 0;
  for (const auto& bytes : encoded.packets) {
    media::SymphoniaPacket packet{};
    packet.timestamp_us = decoded_frames * 1000000 / 48000;
    packet.duration_us = 1024 * 1000000 / 48000;
    for (uint8_t byte : bytes)
      packet.data.push_back(byte);
    auto result = decoder.decoder->decode(packet);
    CHECK_CASE(result.status == media::SymphoniaDecodeStatus::Ok);
    const auto& buffer = *result.buffer;
    CHECK_CASE(buffer.sample_rate == 48000 && buffer.num_frames > 0);
    CHECK_CASE(decoded_frames + buffer.num_frames <= input.size());
    unsigned bytes_per_sample = 0;
    if (buffer.sample_format == media::SymphoniaSampleFormat::S16)
      bytes_per_sample = 2;
    else if (buffer.sample_format == media::SymphoniaSampleFormat::S32 ||
             buffer.sample_format == media::SymphoniaSampleFormat::F32)
      bytes_per_sample = 4;
    CHECK_CASE(bytes_per_sample != 0);
    CHECK_CASE(buffer.data.size() == buffer.num_frames * bytes_per_sample);
    for (size_t i = 0; i < buffer.num_frames; ++i) {
      float value = 0;
      const uint8_t* sample = buffer.data.data() + i * bytes_per_sample;
      if (buffer.sample_format == media::SymphoniaSampleFormat::S16) {
        int16_t integer;
        std::memcpy(&integer, sample, sizeof(integer));
        value = integer / 32768.0f;
      } else if (buffer.sample_format == media::SymphoniaSampleFormat::S32) {
        int32_t integer;
        std::memcpy(&integer, sample, sizeof(integer));
        value = integer / 2147483648.0f;
      } else {
        std::memcpy(&value, sample, sizeof(value));
      }
      CHECK_CASE(value == input[decoded_frames + i] / 32768.0f);
    }
    decoded_frames += buffer.num_frames;
  }
  CHECK_CASE(decoded_frames == input.size());
  media::SymphoniaPacket malformed{};
  malformed.data.push_back(0xff);
  CHECK_CASE(decoder.decoder->decode(malformed).status !=
             media::SymphoniaDecodeStatus::Ok);
  media::SymphoniaDecoderConfig invalid_config{};
  invalid_config.codec = media::SymphoniaAudioCodec::Flac;
  invalid_config.extra_data.push_back(0);
  CHECK_CASE(media::init_symphonia_decoder(invalid_config).status !=
             media::SymphoniaInitStatus::Ok);

  const std::string_view stream(
      reinterpret_cast<const char*>(encoded.file.data()), encoded.file.size());
  media::FlacAudioHandler handler(stream);
  CHECK_CASE(handler.Initialize());
  CHECK_CASE(handler.GetNumChannels() == 1 && handler.GetSampleRate() == 48000);
  auto bus =
      media::AudioBus::Create(1, media::AudioHandler::kDefaultFrameCount);
  size_t position = 0;
  while (!handler.AtEnd()) {
    size_t count = 0;
    CHECK_CASE(handler.CopyTo(bus.get(), &count));
    CHECK_CASE(count > 0 && position + count <= input.size());
    for (size_t i = 0; i < count; ++i)
      CHECK_CASE(bus->channel_span(0)[i] ==
                 input[position + i] * (input[position + i] < 0
                                            ? 1.0f / 32768.0f
                                            : 1.0f / 32767.0f));
    position += count;
  }
  CHECK_CASE(position == input.size());
  handler.Reset();
  size_t count = 0;
  CHECK_CASE(handler.CopyTo(bus.get(), &count));
  CHECK_CASE(count == static_cast<size_t>(bus->frames()));
  for (size_t i = 0; i < count; ++i)
    CHECK_CASE(bus->channel_span(0)[i] ==
               input[i] * (input[i] < 0 ? 1.0f / 32768.0f : 1.0f / 32767.0f));
  media::FlacAudioHandler truncated(stream.substr(0, 8));
  CHECK_CASE(!truncated.Initialize());
  return 0;
}

bool CheckStatus(const leveldb::Status& status) {
  if (!status.ok())
    std::fprintf(stderr, "%s\n", status.ToString().c_str());
  return status.ok();
}

int CheckStorage() {
  base::ScopedTempDir temporary;
  CHECK_CASE(temporary.CreateUniqueTempDir());
  const std::string path = temporary.GetPath().AppendASCII("database").value();
  leveldb::Options options;
  options.create_if_missing = true;
  options.paranoid_checks = true;
  options.compression = leveldb::kSnappyCompression;
  leveldb::DB* raw = nullptr;
  CHECK_CASE(CheckStatus(leveldb::DB::Open(options, path, &raw)));
  std::unique_ptr<leveldb::DB> database(raw);
  leveldb::WriteOptions write;
  write.sync = true;
  const std::string key("binary\0key", 10);
  CHECK_CASE(CheckStatus(database->Put(write, key, "before")));
  const auto* snapshot = database->GetSnapshot();
  CHECK_CASE(snapshot != nullptr);
  leveldb::WriteBatch batch;
  batch.Put(key, "after");
  batch.Put("removed", "value");
  batch.Delete("removed");
  const std::string payload(4096, 'x');
  for (int i = 0; i < 256; ++i)
    batch.Put("entry-" + std::to_string(i), payload + std::to_string(i));
  CHECK_CASE(CheckStatus(database->Write(write, &batch)));
  leveldb::ReadOptions read;
  read.verify_checksums = true;
  read.snapshot = snapshot;
  std::string value;
  CHECK_CASE(CheckStatus(database->Get(read, key, &value)));
  CHECK_CASE(value == "before");
  database->ReleaseSnapshot(snapshot);
  read.snapshot = nullptr;
  CHECK_CASE(CheckStatus(database->Get(read, key, &value)));
  CHECK_CASE(value == "after");
  CHECK_CASE(database->Get(read, "removed", &value).IsNotFound());
  leveldb::DB* locked = nullptr;
  CHECK_CASE(!leveldb::DB::Open(options, path, &locked).ok());
  CHECK_CASE(locked == nullptr);
  database->CompactRange(nullptr, nullptr);
  database.reset();
  std::vector<std::string> files;
  CHECK_CASE(CheckStatus(leveldb::Env::Default()->GetChildren(path, &files)));
  uint64_t table_bytes = 0;
  for (const auto& file : files) {
    if (!file.ends_with(".ldb") && !file.ends_with(".sst"))
      continue;
    uint64_t bytes = 0;
    CHECK_CASE(CheckStatus(
        leveldb::Env::Default()->GetFileSize(path + "/" + file, &bytes)));
    table_bytes += bytes;
  }
  CHECK_CASE(table_bytes > 0 && table_bytes < 256 * payload.size() / 4);
  raw = nullptr;
  CHECK_CASE(CheckStatus(leveldb::DB::Open(options, path, &raw)));
  database.reset(raw);
  CHECK_CASE(CheckStatus(database->Get(read, key, &value)));
  CHECK_CASE(value == "after");
  for (int i = 0; i < 256; ++i) {
    CHECK_CASE(
        CheckStatus(database->Get(read, "entry-" + std::to_string(i), &value)));
    CHECK_CASE(value == payload + std::to_string(i));
  }
  return 0;
}

int main(int argc, char** argv) {
  base::AtExitManager at_exit;
  base::CommandLine::Init(argc, argv);
  CHECK_CASE(argc == 2);
  std::string error;
  std::unique_ptr<rules_cc::cc::runfiles::Runfiles> runfiles(
      rules_cc::cc::runfiles::Runfiles::CreateForTest(&error));
  CHECK_CASE(runfiles);
  base::File data(base::FilePath(runfiles->Rlocation(argv[1])),
                  base::File::FLAG_OPEN | base::File::FLAG_READ);
  CHECK_CASE(data.IsValid());
  CHECK_CASE(base::i18n::InitializeICUWithFileDescriptor(
      data.TakePlatformFile(), base::MemoryMappedFile::Region::kWholeFile));
  base::ThreadPoolInstance::CreateAndStartWithDefaultParams("Media");
  CHECK_CASE(CheckAudio() == 0);
  CHECK_CASE(CheckStorage() == 0);
  base::ThreadPoolInstance::Get()->Shutdown();
  std::puts(
      "Chromium media: FLAC/Symphonia PCM, reset/rejection; LevelDB snapshots, "
      "locks, compressed persistence passed");
  return 0;
}
