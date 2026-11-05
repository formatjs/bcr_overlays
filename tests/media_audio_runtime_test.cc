#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>

#include "opus.h"
extern "C" {
#include "libavcodec/avcodec.h"
#include "libavformat/avformat.h"
#include "libavutil/channel_layout.h"
}

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

int CheckOpus() {
  constexpr int kFrame = 960;
  constexpr int kFrames = 12;
  int error = 0;
  OpusEncoder* encoder =
      opus_encoder_create(48000, 1, OPUS_APPLICATION_AUDIO, &error);
  CHECK_CASE(encoder && error == OPUS_OK);
  OpusDecoder* decoder = opus_decoder_create(48000, 1, &error);
  CHECK_CASE(decoder && error == OPUS_OK);
  CHECK_CASE(opus_encoder_ctl(encoder, OPUS_SET_BITRATE(64000)) == OPUS_OK);
  CHECK_CASE(opus_encoder_ctl(encoder, OPUS_SET_COMPLEXITY(5)) == OPUS_OK);
  int delay = 0;
  CHECK_CASE(opus_encoder_ctl(encoder, OPUS_GET_LOOKAHEAD(&delay)) == OPUS_OK);
  CHECK_CASE(delay >= 0 && delay < kFrame);
  std::vector<float> input(kFrame * kFrames), output(input.size());
  for (size_t i = 0; i < input.size(); ++i)
    input[i] = 0.4f * std::sin(2.0 * 3.141592653589793 * 440 * i / 48000.0) +
               0.1f * std::sin(2.0 * 3.141592653589793 * 1000 * i / 48000.0);
  uint8_t packet[1500];
  for (int frame = 0; frame < kFrames; ++frame) {
    const int size = opus_encode_float(encoder, input.data() + frame * kFrame,
                                       kFrame, packet, sizeof(packet));
    CHECK_CASE(size > 0);
    CHECK_CASE(opus_packet_get_nb_samples(packet, size, 48000) == kFrame);
    CHECK_CASE(opus_decode_float(decoder, packet, size,
                                 output.data() + frame * kFrame, kFrame,
                                 0) == kFrame);
  }
  double noise = 0, signal = 0;
  for (size_t i = 2 * kFrame + delay; i < input.size(); ++i) {
    CHECK_CASE(std::isfinite(output[i]));
    const double expected = input[i - delay];
    noise += (output[i] - expected) * (output[i] - expected);
    signal += expected * expected;
  }
  CHECK_CASE(signal > 100 && noise / signal < 0.05);
  CHECK_CASE(opus_decode_float(decoder, nullptr, 0, output.data(), kFrame, 0) ==
             kFrame);
  for (int i = 0; i < kFrame; ++i)
    CHECK_CASE(std::isfinite(output[i]) && std::abs(output[i]) < 2.0f);
  const uint8_t invalid[] = {0xff};
  CHECK_CASE(opus_decode_float(decoder, invalid, sizeof(invalid), output.data(),
                               kFrame, 0) == OPUS_INVALID_PACKET);
  opus_encoder_destroy(encoder);
  opus_decoder_destroy(decoder);
  return 0;
}

struct Reader {
  std::vector<uint8_t> bytes;
  size_t position = 0;
  static int Read(void* opaque, uint8_t* output, int capacity) {
    auto& self = *static_cast<Reader*>(opaque);
    const size_t count = std::min(static_cast<size_t>(capacity),
                                  self.bytes.size() - self.position);
    if (!count)
      return AVERROR_EOF;
    std::memcpy(output, self.bytes.data() + self.position, count);
    self.position += count;
    return static_cast<int>(count);
  }
  static int64_t Seek(void* opaque, int64_t offset, int whence) {
    auto& self = *static_cast<Reader*>(opaque);
    if (whence == AVSEEK_SIZE)
      return self.bytes.size();
    whence &= ~AVSEEK_FORCE;
    if (whence == SEEK_CUR)
      offset += self.position;
    else if (whence == SEEK_END)
      offset += self.bytes.size();
    else if (whence != SEEK_SET)
      return AVERROR(EINVAL);
    if (offset < 0 || static_cast<uint64_t>(offset) > self.bytes.size())
      return AVERROR(EINVAL);
    self.position = offset;
    return offset;
  }
  void Word(uint32_t value, unsigned count) {
    for (unsigned i = 0; i < count; ++i)
      bytes.push_back(static_cast<uint8_t>(value >> (8 * i)));
  }
  void Tag(const char* value) { bytes.insert(bytes.end(), value, value + 4); }
};

int CheckFFmpeg() {
  CHECK_CASE((avcodec_version() >> 16) == 62);
  std::vector<int16_t> input(2048);
  for (size_t i = 0; i < input.size(); ++i)
    input[i] = static_cast<int16_t>((i * 997) % 60001 - 30000);
  Reader reader;
  reader.Tag("RIFF");
  reader.Word(36 + 2 * input.size(), 4);
  reader.Tag("WAVE");
  reader.Tag("fmt ");
  reader.Word(16, 4);
  reader.Word(1, 2);
  reader.Word(1, 2);
  reader.Word(48000, 4);
  reader.Word(96000, 4);
  reader.Word(2, 2);
  reader.Word(16, 2);
  reader.Tag("data");
  reader.Word(2 * input.size(), 4);
  for (int16_t sample : input)
    reader.Word(static_cast<uint16_t>(sample), 2);
  AVIOContext* io =
      avio_alloc_context(static_cast<uint8_t*>(av_malloc(4096)), 4096, 0,
                         &reader, Reader::Read, nullptr, Reader::Seek);
  CHECK_CASE(io != nullptr);
  AVFormatContext* format = avformat_alloc_context();
  CHECK_CASE(format != nullptr);
  format->pb = io;
  format->flags |= AVFMT_FLAG_CUSTOM_IO;
  CHECK_CASE(avformat_open_input(&format, nullptr, av_find_input_format("wav"),
                                 nullptr) == 0);
  CHECK_CASE(avformat_find_stream_info(format, nullptr) >= 0);
  CHECK_CASE(format->nb_streams == 1);
  const auto* parameters = format->streams[0]->codecpar;
  CHECK_CASE(parameters->codec_id == AV_CODEC_ID_PCM_S16LE);
  CHECK_CASE(parameters->sample_rate == 48000 &&
             parameters->ch_layout.nb_channels == 1);
  const AVCodec* codec = avcodec_find_decoder(parameters->codec_id);
  CHECK_CASE(codec != nullptr);
  AVCodecContext* context = avcodec_alloc_context3(codec);
  CHECK_CASE(context != nullptr);
  CHECK_CASE(avcodec_parameters_to_context(context, parameters) == 0);
  CHECK_CASE(avcodec_open2(context, codec, nullptr) == 0);
  AVPacket* packet = av_packet_alloc();
  AVFrame* frame = av_frame_alloc();
  CHECK_CASE(packet && frame);
  std::vector<int16_t> output;
  int read_result;
  while ((read_result = av_read_frame(format, packet)) >= 0) {
    CHECK_CASE(avcodec_send_packet(context, packet) == 0);
    int result;
    while ((result = avcodec_receive_frame(context, frame)) >= 0) {
      CHECK_CASE(frame->format == AV_SAMPLE_FMT_S16);
      const auto* samples = reinterpret_cast<const int16_t*>(frame->data[0]);
      output.insert(output.end(), samples, samples + frame->nb_samples);
      av_frame_unref(frame);
    }
    CHECK_CASE(result == AVERROR(EAGAIN));
    av_packet_unref(packet);
  }
  CHECK_CASE(read_result == AVERROR_EOF);
  CHECK_CASE(output == input);
  CHECK_CASE(avcodec_send_packet(context, nullptr) == 0);
  CHECK_CASE(avcodec_receive_frame(context, frame) == AVERROR_EOF);
  av_frame_free(&frame);
  av_packet_free(&packet);
  avcodec_free_context(&context);
  avformat_close_input(&format);
  av_freep(&io->buffer);
  avio_context_free(&io);
  return 0;
}

int main() {
  CHECK_CASE(CheckOpus() == 0);
  CHECK_CASE(CheckFFmpeg() == 0);
  std::puts(
      "Opus: audio, packet loss, invalid packet; Chromium FFmpeg: WAV "
      "demux/PCM decode passed");
  return 0;
}
