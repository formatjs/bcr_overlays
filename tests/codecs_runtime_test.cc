#include <array>
#include <csetjmp>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <type_traits>
#include <vector>

extern "C" {
#include "third_party/libjpeg_turbo/src/jpeglib.h"
}
#include "third_party/libwebp/src/src/webp/decode.h"
#include "third_party/libwebp/src/src/webp/demux.h"
#include "third_party/libwebp/src/src/webp/encode.h"
#include "third_party/libwebp/src/src/webp/mux.h"
#include "third_party/wuffs/src/release/c/wuffs-v0.3.c"

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

struct JpegError {
  jpeg_error_mgr manager;
  std::jmp_buf jump;
};

bool RejectJpeg(const unsigned char* bytes, size_t size) {
  jpeg_decompress_struct decoder{};
  JpegError error{};
  decoder.err = jpeg_std_error(&error.manager);
  error.manager.error_exit = [](j_common_ptr context) {
    std::longjmp(reinterpret_cast<JpegError*>(context->err)->jump, 1);
  };
  if (setjmp(error.jump)) {
    jpeg_destroy_decompress(&decoder);
    return true;
  }
  jpeg_create_decompress(&decoder);
  jpeg_mem_src(&decoder, bytes, size);
  jpeg_read_header(&decoder, TRUE);
  jpeg_destroy_decompress(&decoder);
  return false;
}

int CheckJpeg8() {
  jpeg_compress_struct encoder{};
  jpeg_error_mgr error{};
  encoder.err = jpeg_std_error(&error);
  jpeg_create_compress(&encoder);
  unsigned char* bytes = nullptr;
  unsigned long size = 0;
  jpeg_mem_dest(&encoder, &bytes, &size);
  encoder.image_width = 16;
  encoder.image_height = 16;
  encoder.input_components = 3;
  encoder.in_color_space = JCS_RGB;
  jpeg_set_defaults(&encoder);
  jpeg_set_quality(&encoder, 95, TRUE);
  jpeg_start_compress(&encoder, TRUE);
  std::array<JSAMPLE, 48> row;
  for (size_t i = 0; i < row.size(); ++i)
    row[i] = (i % 3 == 2) ? 240 : 20;
  while (encoder.next_scanline < encoder.image_height) {
    JSAMPROW source = row.data();
    CHECK_CASE(jpeg_write_scanlines(&encoder, &source, 1) == 1);
  }
  jpeg_finish_compress(&encoder);
  jpeg_destroy_compress(&encoder);

  jpeg_decompress_struct decoder{};
  decoder.err = jpeg_std_error(&error);
  jpeg_create_decompress(&decoder);
  jpeg_mem_src(&decoder, bytes, size);
  CHECK_CASE(jpeg_read_header(&decoder, TRUE) == JPEG_HEADER_OK);
  decoder.out_color_space = JCS_RGB;
  CHECK_CASE(jpeg_start_decompress(&decoder));
  CHECK_CASE(decoder.output_width == 16 && decoder.output_height == 16);
  CHECK_CASE(decoder.output_components == 3);
  while (decoder.output_scanline < decoder.output_height) {
    JSAMPROW destination = row.data();
    CHECK_CASE(jpeg_read_scanlines(&decoder, &destination, 1) == 1);
    for (size_t i = 0; i < row.size(); ++i) {
      CHECK_CASE(std::abs(int(row[i]) - (i % 3 == 2 ? 240 : 20)) <= 3);
    }
  }
  CHECK_CASE(jpeg_finish_decompress(&decoder));
  jpeg_destroy_decompress(&decoder);
  CHECK_CASE(RejectJpeg(bytes, 4));
  std::free(bytes);
  return 0;
}

template <int Precision>
int CheckLosslessJpeg() {
  using Sample = std::conditional_t<Precision == 12, J12SAMPLE, J16SAMPLE>;
  const Sample maximum = (1u << Precision) - 1;
  std::array<Sample, 8> pixels{
      0, 1, Sample(maximum / 2), maximum, maximum, 0, 123, 2048};
  jpeg_error_mgr error{};
  jpeg_compress_struct encoder{};
  encoder.err = jpeg_std_error(&error);
  jpeg_create_compress(&encoder);
  unsigned char* bytes = nullptr;
  unsigned long size = 0;
  jpeg_mem_dest(&encoder, &bytes, &size);
  encoder.image_width = 4;
  encoder.image_height = 2;
  encoder.input_components = 1;
  encoder.in_color_space = JCS_GRAYSCALE;
  jpeg_set_defaults(&encoder);
  encoder.data_precision = Precision;
  jpeg_enable_lossless(&encoder, 1, 0);
  jpeg_start_compress(&encoder, TRUE);
  while (encoder.next_scanline < encoder.image_height) {
    Sample* row = pixels.data() + encoder.next_scanline * 4;
    if constexpr (Precision == 12) {
      CHECK_CASE(jpeg12_write_scanlines(&encoder, &row, 1) == 1);
    } else {
      CHECK_CASE(jpeg16_write_scanlines(&encoder, &row, 1) == 1);
    }
  }
  jpeg_finish_compress(&encoder);
  jpeg_destroy_compress(&encoder);
  jpeg_decompress_struct decoder{};
  decoder.err = jpeg_std_error(&error);
  jpeg_create_decompress(&decoder);
  jpeg_mem_src(&decoder, bytes, size);
  CHECK_CASE(jpeg_read_header(&decoder, TRUE) == JPEG_HEADER_OK);
  CHECK_CASE(decoder.data_precision == Precision);
  CHECK_CASE(jpeg_start_decompress(&decoder));
  CHECK_CASE(decoder.output_width == 4 && decoder.output_height == 2);
  std::array<Sample, 8> decoded{};
  while (decoder.output_scanline < decoder.output_height) {
    Sample* row = decoded.data() + decoder.output_scanline * 4;
    if constexpr (Precision == 12) {
      CHECK_CASE(jpeg12_read_scanlines(&decoder, &row, 1) == 1);
    } else {
      CHECK_CASE(jpeg16_read_scanlines(&decoder, &row, 1) == 1);
    }
  }
  CHECK_CASE(decoded == pixels);
  CHECK_CASE(jpeg_finish_decompress(&decoder));
  jpeg_destroy_decompress(&decoder);
  std::free(bytes);
  return 0;
}

int CheckWebP() {
  constexpr std::array<uint8_t, 16> pixels{255, 0, 0,   255, 0, 255, 0, 128,
                                           0,   0, 255, 64,  0, 0,   0, 255};
  uint8_t* encoded = nullptr;
  const size_t size = WebPEncodeLosslessRGBA(pixels.data(), 2, 2, 8, &encoded);
  CHECK_CASE(size > 0 && encoded);
  int width = 0, height = 0;
  uint8_t* decoded = WebPDecodeRGBA(encoded, size, &width, &height);
  CHECK_CASE(decoded && width == 2 && height == 2);
  CHECK_CASE(std::memcmp(decoded, pixels.data(), pixels.size()) == 0);
  WebPFree(decoded);
  std::array<uint8_t, 15> too_small{};
  CHECK_CASE(!WebPDecodeRGBAInto(encoded, size, too_small.data(),
                                 too_small.size(), 8));
  CHECK_CASE(!WebPDecodeRGBA(encoded, size / 2, &width, &height));

  auto second = pixels;
  second[0] = 0;
  second[2] = 255;
  uint8_t* encoded_second = nullptr;
  const size_t second_size =
      WebPEncodeLosslessRGBA(second.data(), 2, 2, 8, &encoded_second);
  CHECK_CASE(second_size > 0);
  WebPMux* mux = WebPMuxNew();
  CHECK_CASE(mux);
  WebPMuxAnimParams parameters{0, 2};
  CHECK_CASE(WebPMuxSetAnimationParams(mux, &parameters) == WEBP_MUX_OK);
  WebPMuxFrameInfo frame{};
  frame.id = WEBP_CHUNK_ANMF;
  frame.duration = 16;
  frame.blend_method = WEBP_MUX_NO_BLEND;
  frame.bitstream = {encoded, size};
  CHECK_CASE(WebPMuxPushFrame(mux, &frame, 1) == WEBP_MUX_OK);
  frame.duration = 24;
  frame.bitstream = {encoded_second, second_size};
  CHECK_CASE(WebPMuxPushFrame(mux, &frame, 1) == WEBP_MUX_OK);
  WebPData animation{};
  CHECK_CASE(WebPMuxAssemble(mux, &animation) == WEBP_MUX_OK);
  WebPDemuxer* reader = WebPDemux(&animation);
  CHECK_CASE(reader);
  CHECK_CASE(WebPDemuxGetI(reader, WEBP_FF_FRAME_COUNT) == 2);
  CHECK_CASE(WebPDemuxGetI(reader, WEBP_FF_LOOP_COUNT) == 2);
  WebPIterator iterator;
  for (int index = 1; index <= 2; ++index) {
    CHECK_CASE(WebPDemuxGetFrame(reader, index, &iterator));
    CHECK_CASE(iterator.duration == (index == 1 ? 16 : 24));
    decoded = WebPDecodeRGBA(iterator.fragment.bytes, iterator.fragment.size,
                             &width, &height);
    CHECK_CASE(decoded && width == 2 && height == 2);
    CHECK_CASE(std::memcmp(decoded, index == 1 ? pixels.data() : second.data(),
                           pixels.size()) == 0);
    WebPFree(decoded);
    WebPDemuxReleaseIterator(&iterator);
  }
  CHECK_CASE(!WebPDemuxGetFrame(reader, 3, &iterator));
  WebPDemuxDelete(reader);
  WebPDataClear(&animation);
  WebPMuxDelete(mux);
  WebPFree(encoded);
  WebPFree(encoded_second);
  return 0;
}

int CheckGif() {
  std::array<uint8_t, 35> gif{'G', 'I', 'F', '8', '9',  'a',  2, 0,  1,
                              0,   128, 0,   0,   255,  0,    0, 0,  255,
                              0,   ',', 0,   0,   0,    0,    2, 0,  1,
                              0,   0,   2,   2,   0x44, 0x0a, 0, ';'};
  auto source = wuffs_base__ptr_u8__reader(gif.data(), gif.size(), true);
  auto decoder = wuffs_gif__decoder::alloc();
  CHECK_CASE(decoder);
  wuffs_base__image_config config{};
  CHECK_CASE(decoder->decode_image_config(&config, &source).is_ok());
  CHECK_CASE(config.pixcfg.width() == 2 && config.pixcfg.height() == 1);
  wuffs_base__pixel_config format;
  format.set(WUFFS_BASE__PIXEL_FORMAT__RGBA_NONPREMUL, 0, 2, 1);
  std::array<uint8_t, 8> pixels{};
  wuffs_base__pixel_buffer destination{};
  CHECK_CASE(destination
                 .set_from_slice(&format, wuffs_base__make_slice_u8(
                                              pixels.data(), pixels.size()))
                 .is_ok());
  std::vector<uint8_t> work(decoder->workbuf_len().max_incl);
  CHECK_CASE(
      decoder
          ->decode_frame(&destination, &source, WUFFS_BASE__PIXEL_BLEND__SRC,
                         wuffs_base__make_slice_u8(work.data(), work.size()),
                         nullptr)
          .is_ok());
  CHECK_CASE(
      (pixels == std::array<uint8_t, 8>{255, 0, 0, 255, 0, 255, 0, 255}));
  auto bad = wuffs_gif__decoder::alloc();
  source = wuffs_base__ptr_u8__reader(gif.data(), 8, true);
  CHECK_CASE(!bad->decode_image_config(&config, &source).is_ok());
  return 0;
}

int main() {
  CHECK_CASE(CheckJpeg8() == 0);
  CHECK_CASE(CheckLosslessJpeg<12>() == 0);
  CHECK_CASE(CheckLosslessJpeg<16>() == 0);
  CHECK_CASE(CheckWebP() == 0);
  CHECK_CASE(CheckGif() == 0);
  return 0;
}
