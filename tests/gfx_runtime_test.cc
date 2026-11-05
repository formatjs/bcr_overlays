#include <unistd.h>
#include <array>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <string>

#include "base/at_exit.h"
#include "base/files/file_util.h"
#include "base/files/scoped_file.h"
#include "base/files/scoped_temp_dir.h"
#include "base/memory/ref_counted_memory.h"
#include "partition_alloc/partition_alloc.h"
#include "third_party/libdrm/src/include/drm/drm_fourcc.h"
#include "third_party/libdrm/src/xf86drm.h"
#include "third_party/libsync/src/include/sync/sync.h"
#include "third_party/skia/include/codec/SkCodec.h"
#include "third_party/skia/include/codec/SkWebpDecoder.h"
#include "third_party/skia/include/core/SkBitmap.h"
#include "third_party/skia/include/core/SkColorSpace.h"
#include "third_party/skia/include/core/SkData.h"
#include "third_party/skia/include/core/SkGraphics.h"
#include "third_party/zlib/google/compression_utils.h"
#include "ui/base/resource/data_pack.h"
#include "ui/gfx/codec/jpeg_codec.h"
#include "ui/gfx/codec/png_codec.h"
#include "ui/gfx/codec/webp_codec.h"
#include "ui/gfx/geometry/size.h"
#include "ui/gfx/gpu_fence_handle.h"
#include "ui/gfx/icc_profile.h"
#include "ui/gfx/image/image.h"

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

int CheckImages() {
  const std::array<uint8_t, 8> rgba{255, 0, 0, 128, 0, 255, 0, 255};
  auto png = gfx::PNGCodec::Encode(rgba.data(), gfx::PNGCodec::FORMAT_RGBA,
                                   gfx::Size(2, 1), 8, false, {});
  CHECK_CASE(png);
  auto decoded = gfx::PNGCodec::Decode(*png, gfx::PNGCodec::FORMAT_RGBA);
  CHECK_CASE(decoded && decoded->width == 2 && decoded->height == 1);
  CHECK_CASE(decoded->output.size() == rgba.size());
  CHECK_CASE(std::memcmp(decoded->output.data(), rgba.data(), rgba.size()) ==
             0);
  gfx::Image image = gfx::Image::CreateFrom1xPNGBytes(*png);
  CHECK_CASE(!image.IsEmpty() && image.Width() == 2 && image.Height() == 1);
  SkBitmap bitmap = image.AsBitmap();
  CHECK_CASE(bitmap.getColor(0, 0) == SkColorSetARGB(128, 255, 0, 0));
  CHECK_CASE(bitmap.getColor(1, 0) == SK_ColorGREEN);
  auto encoded = gfx::Image::CreateFrom1xBitmap(bitmap).As1xPNGBytes();
  CHECK_CASE(encoded && encoded->size() > 8);
  auto round_trip = gfx::PNGCodec::Decode(base::span(*encoded));
  CHECK_CASE(round_trip.getColor(0, 0) == bitmap.getColor(0, 0));
  CHECK_CASE(round_trip.getColor(1, 0) == bitmap.getColor(1, 0));
  CHECK_CASE(!gfx::PNGCodec::Decode(base::span(*png).first<8>(),
                                    gfx::PNGCodec::FORMAT_RGBA));

  SkBitmap solid;
  CHECK_CASE(solid.tryAllocPixels(SkImageInfo::MakeN32Premul(8, 8)));
  solid.eraseColor(SkColorSetRGB(64, 128, 192));
  auto jpeg = gfx::JPEGCodec::Encode(solid, 100);
  CHECK_CASE(jpeg);
  SkBitmap lossy = gfx::JPEGCodec::Decode(*jpeg);
  CHECK_CASE(lossy.width() == 8 && lossy.height() == 8);
  for (int y = 0; y < 8; ++y) {
    for (int x = 0; x < 8; ++x) {
      SkColor pixel = lossy.getColor(x, y);
      CHECK_CASE(std::abs(int(SkColorGetR(pixel)) - 64) <= 3);
      CHECK_CASE(std::abs(int(SkColorGetG(pixel)) - 128) <= 3);
      CHECK_CASE(std::abs(int(SkColorGetB(pixel)) - 192) <= 3);
    }
  }
  CHECK_CASE(gfx::JPEGCodec::Decode(base::span(*jpeg).first<8>()).isNull());
  auto webp = gfx::WebpCodec::Encode(solid, 90);
  CHECK_CASE(webp && webp->size() > 12);
  CHECK_CASE(std::memcmp(webp->data(), "RIFF", 4) == 0);
  CHECK_CASE(std::memcmp(webp->data() + 8, "WEBP", 4) == 0);
  SkCodec::Result webp_result;
  auto webp_decoder = SkWebpDecoder::Decode(
      SkData::MakeWithCopy(webp->data(), webp->size()), &webp_result);
  CHECK_CASE(webp_decoder && webp_result == SkCodec::kSuccess);
  SkBitmap webp_pixels;
  CHECK_CASE(webp_pixels.tryAllocPixels(solid.info()));
  CHECK_CASE(
      webp_decoder->getPixels(webp_pixels.info(), webp_pixels.getPixels(),
                              webp_pixels.rowBytes()) == SkCodec::kSuccess);
  for (int y = 0; y < 8; ++y) {
    for (int x = 0; x < 8; ++x) {
      const SkColor pixel = webp_pixels.getColor(x, y);
      CHECK_CASE(std::abs(int(SkColorGetR(pixel)) - 64) <= 4);
      CHECK_CASE(std::abs(int(SkColorGetG(pixel)) - 128) <= 4);
      CHECK_CASE(std::abs(int(SkColorGetB(pixel)) - 192) <= 4);
    }
  }

  auto profile = gfx::ICCProfile::FromColorSpace(gfx::ColorSpace::CreateSRGB());
  CHECK_CASE(profile.IsValid());
  const auto icc = profile.GetData();
  CHECK_CASE(!icc.empty());
  auto parsed = gfx::ICCProfile::FromData(icc.data(), icc.size());
  CHECK_CASE(parsed.IsValid() &&
             parsed.GetColorSpace().ToSkColorSpace()->isSRGB());
  CHECK_CASE(!gfx::ICCProfile::FromData("invalid", 7).IsValid());
  return 0;
}

int CheckResources() {
  base::ScopedTempDir directory;
  CHECK_CASE(directory.CreateUniqueTempDir());
  const std::string binary("a\0b\xff", 4);
  const std::map<uint16_t, std::string_view> resources{
      {7, binary}, {10, binary}, {25, "<html>native Bazel</html>"}};
  auto path = directory.GetPath().AppendASCII("resources.pak");
  CHECK_CASE(
      ui::DataPack::WritePack(path, resources, ui::ResourceHandle::BINARY));
  ui::DataPack pack(ui::k100Percent);
  CHECK_CASE(pack.LoadFromPath(path));
  CHECK_CASE(pack.GetStringView(7) == binary);
  CHECK_CASE(pack.GetStringView(10) == binary);
  CHECK_CASE(pack.GetStringView(25) == "<html>native Bazel</html>");
  CHECK_CASE(!pack.HasResource(8) && !pack.GetStringView(8));
  std::string data;
  CHECK_CASE(base::ReadFileToString(path, &data));
  std::string gzip;
  CHECK_CASE(compression::GzipCompress(base::span(data), &gzip));
  auto compressed_path = directory.GetPath().AppendASCII("resources.pak.gz");
  CHECK_CASE(base::WriteFile(compressed_path, gzip));
  ui::DataPack compressed(ui::k100Percent);
  CHECK_CASE(compressed.LoadFromPath(compressed_path));
  CHECK_CASE(compressed.GetStringView(7) == binary);
  ui::DataPack truncated(ui::k100Percent);
  CHECK_CASE(!truncated.LoadFromBuffer(base::as_byte_span(data).first<8>()));
  return 0;
}

int CheckLinuxGraphics() {
  CHECK_CASE(sync_wait(-1, 0) == -1 && errno == EINVAL);
  int fds[2];
  CHECK_CASE(pipe(fds) == 0);
  base::ScopedFD writer(fds[1]);
  gfx::GpuFenceHandle original;
  original.Adopt(base::ScopedFD(fds[0]));
  auto clone = original.Clone();
  CHECK_CASE(!original.is_null() && !clone.is_null());
  original.Reset();
  CHECK_CASE(original.is_null() && !clone.is_null());
  CHECK_CASE(sync_wait(clone.Peek(), 0) == -1 && errno == ETIME);
  CHECK_CASE(write(writer.get(), "x", 1) == 1);
  CHECK_CASE(sync_wait(clone.Peek(), 100) == 0);
  auto released = clone.Release();
  CHECK_CASE(clone.is_null() && released.is_valid());
  char value = 0;
  CHECK_CASE(read(released.get(), &value, 1) == 1 && value == 'x');
  char* modifier = drmGetFormatModifierName(DRM_FORMAT_MOD_LINEAR);
  CHECK_CASE(modifier && std::string(modifier) == "LINEAR");
  std::free(modifier);
  CHECK_CASE(drmGetVersion(-1) == nullptr);
  return 0;
}

int main() {
  partition_alloc::PartitionAllocGlobalInit([](size_t) { std::abort(); });
  base::AtExitManager at_exit;
  SkGraphics::Init();
  ui::test::ScopedSetSupportedResourceScaleFactors scales(
      {ui::k100Percent, ui::k200Percent});
  CHECK_CASE(CheckImages() == 0);
  CHECK_CASE(CheckResources() == 0);
  CHECK_CASE(CheckLinuxGraphics() == 0);
  return 0;
}
