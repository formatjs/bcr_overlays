#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iterator>
#include <memory>
#include <string>
#include <vector>

#include "rules_cc/cc/runfiles/runfiles.h"
#include "third_party/crabbyavif/src/include/avif/avif.h"

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

namespace avif = crabbyavif;

using Decoder = std::unique_ptr<avif::avifDecoder,
                                decltype(&avif::crabby_avifDecoderDestroy)>;

Decoder NewDecoder() {
  Decoder decoder(avif::crabby_avifDecoderCreate(),
                  avif::crabby_avifDecoderDestroy);
  if (decoder) {
    decoder->maxThreads = 2;
    decoder->codecChoice = avif::AVIF_CODEC_CHOICE_DAV1D;
  }
  return decoder;
}

int ReadPixels(const avif::avifImage* image, std::vector<uint8_t>& pixels) {
  avif::avifRGBImage rgb{};
  avif::crabby_avifRGBImageSetDefaults(&rgb, image);
  rgb.format = avif::AVIF_RGB_FORMAT_RGBA;
  rgb.depth = 8;
  CHECK_CASE(avif::crabby_avifRGBImageAllocatePixels(&rgb) ==
             avif::AVIF_RESULT_OK);
  CHECK_CASE(avif::crabby_avifImageYUVToRGB(image, &rgb) ==
             avif::AVIF_RESULT_OK);
  CHECK_CASE(rgb.width == image->width && rgb.height == image->height);
  CHECK_CASE(rgb.rowBytes >= rgb.width * 4);
  pixels.clear();
  for (uint32_t y = 0; y < rgb.height; ++y) {
    const uint8_t* row = rgb.pixels + y * rgb.rowBytes;
    pixels.insert(pixels.end(), row, row + rgb.width * 4);
    const uint32_t maximum = (1u << image->depth) - 1;
    const uint32_t sample_bytes = image->depth > 8 ? 2 : 1;
    if (image->alphaPlane)
      CHECK_CASE(image->alphaRowBytes >= image->width * sample_bytes);
    for (uint32_t x = 0; x < rgb.width; ++x) {
      uint32_t source_alpha = maximum;
      if (image->alphaPlane) {
        const uint8_t* alpha =
            image->alphaPlane + y * image->alphaRowBytes + x * sample_bytes;
        if (sample_bytes == 1) {
          source_alpha = *alpha;
        } else {
          uint16_t sample;
          std::memcpy(&sample, alpha, sizeof(sample));
          source_alpha = sample;
        }
      }
      CHECK_CASE(source_alpha <= maximum);
      if (source_alpha == 0 || source_alpha == maximum) {
        CHECK_CASE(row[x * 4 + 3] == (source_alpha == 0 ? 0 : 255));
      } else {
        // Allow one output level for alpha depth conversion.
        CHECK_CASE(std::abs(row[x * 4 + 3] - source_alpha * 255.0 / maximum) <=
                   1.0);
      }
    }
  }
  avif::crabby_avifRGBImageFreePixels(&rgb);
  return 0;
}

int CheckFixture(const std::string& path, uint32_t depth, int frames) {
  std::ifstream input(path, std::ios::binary);
  CHECK_CASE(input.good());
  std::vector<uint8_t> bytes(std::istreambuf_iterator<char>(input), {});
  CHECK_CASE(bytes.size() > 32);
  auto decoder = NewDecoder();
  CHECK_CASE(decoder);
  CHECK_CASE(avif::crabby_avifDecoderSetIOMemory(decoder.get(), bytes.data(),
                                                 bytes.size()) ==
             avif::AVIF_RESULT_OK);
  CHECK_CASE(avif::crabby_avifDecoderParse(decoder.get()) ==
             avif::AVIF_RESULT_OK);
  CHECK_CASE(decoder->imageCount == frames);
  CHECK_CASE(decoder->image && decoder->image->depth == depth);
  CHECK_CASE(decoder->image->width > 0 && decoder->image->height > 0);
  std::vector<uint8_t> first;
  std::vector<uint8_t> pixels;
  bool changed = false;
  for (int frame = 0; frame < frames; ++frame) {
    CHECK_CASE(avif::crabby_avifDecoderNextImage(decoder.get()) ==
               avif::AVIF_RESULT_OK);
    CHECK_CASE(decoder->imageIndex == frame);
    CHECK_CASE(ReadPixels(decoder->image, pixels) == 0);
    if (frame == 0)
      first = pixels;
    else
      changed |= pixels != first;
  }
  CHECK_CASE(frames == 1 || changed);
  CHECK_CASE(avif::crabby_avifDecoderNextImage(decoder.get()) ==
             avif::AVIF_RESULT_NO_IMAGES_REMAINING);
  CHECK_CASE(avif::crabby_avifDecoderNthImage(decoder.get(), 0) ==
             avif::AVIF_RESULT_OK);
  CHECK_CASE(ReadPixels(decoder->image, pixels) == 0 && pixels == first);
  CHECK_CASE(avif::crabby_avifDecoderNthImage(decoder.get(), frames + 10) !=
             avif::AVIF_RESULT_OK);
  auto truncated = NewDecoder();
  CHECK_CASE(truncated);
  CHECK_CASE(avif::crabby_avifDecoderSetIOMemory(truncated.get(), bytes.data(),
                                                 16) == avif::AVIF_RESULT_OK);
  CHECK_CASE(avif::crabby_avifDecoderParse(truncated.get()) !=
             avif::AVIF_RESULT_OK);
  return 0;
}

int main(int argc, char** argv) {
  CHECK_CASE(argc == 4);
  std::string error;
  std::unique_ptr<rules_cc::cc::runfiles::Runfiles> runfiles(
      rules_cc::cc::runfiles::Runfiles::CreateForTest(&error));
  CHECK_CASE(runfiles);
  CHECK_CASE(CheckFixture(runfiles->Rlocation(argv[1]), 8, 5) == 0);
  CHECK_CASE(CheckFixture(runfiles->Rlocation(argv[2]), 10, 1) == 0);
  CHECK_CASE(CheckFixture(runfiles->Rlocation(argv[3]), 12, 5) == 0);
  std::puts(
      "CrabbyAVIF: native dav1d/libyuv 8/10/12-bit decode, RGB, animation, "
      "seeking and truncation rejection passed");
  return 0;
}
