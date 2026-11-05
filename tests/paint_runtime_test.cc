#include <array>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

#include "base/at_exit.h"
#include "cc/paint/paint_flags.h"
#include "cc/paint/paint_op.h"
#include "cc/paint/paint_op_buffer.h"
#include "cc/paint/paint_op_buffer_serializer.h"
#include "cc/paint/paint_record.h"
#include "components/crash/core/common/crash_key.h"
#include "partition_alloc/partition_alloc.h"
#include "third_party/skia/include/core/SkBitmap.h"
#include "third_party/skia/include/core/SkCanvas.h"
#include "third_party/skia/include/core/SkGraphics.h"
#include "ui/gfx/color_space.h"

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

int CheckPixels(const cc::PaintOpBuffer& buffer) {
  SkBitmap bitmap;
  CHECK_CASE(bitmap.tryAllocPixels(SkImageInfo::MakeN32Premul(32, 32)));
  SkCanvas canvas(bitmap);
  buffer.Playback(&canvas);
  for (int y = 0; y < 32; ++y) {
    for (int x = 0; x < 32; ++x) {
      const SkColor expected =
          x >= 4 && x < 10 && y >= 4 && y < 10     ? SK_ColorRED
          : x >= 24 && x < 28 && y >= 24 && y < 28 ? SK_ColorBLUE
                                                   : SK_ColorWHITE;
      CHECK_CASE(bitmap.getColor(x, y) == expected);
    }
  }
  return 0;
}

int main() {
  partition_alloc::PartitionAllocGlobalInit([](size_t) { std::abort(); });
  base::AtExitManager at_exit;
  SkGraphics::Init();
  cc::PaintFlags red;
  red.setColor(SK_ColorRED);
  red.setAntiAlias(false);
  cc::PaintFlags blue = red;
  blue.setColor(SK_ColorBLUE);

  cc::PaintOpBuffer child;
  child.push<cc::DrawRectOp>(SkRect::MakeWH(8, 8), red);
  cc::PaintOpBuffer buffer;
  buffer.push<cc::DrawColorOp>(SkColors::kWhite, SkBlendMode::kSrc);
  buffer.push<cc::SaveOp>();
  buffer.push<cc::ClipRectOp>(SkRect::MakeXYWH(4, 4, 16, 16),
                              SkClipOp::kIntersect, false);
  buffer.push<cc::TranslateOp>(2.f, 2.f);
  buffer.push<cc::DrawRecordOp>(child.ReleaseAsRecord());
  buffer.push<cc::RestoreOp>();
  buffer.push<cc::DrawRectOp>(SkRect::MakeXYWH(24, 24, 4, 4), blue);
  CHECK_CASE(CheckPixels(buffer) == 0);

  // Exercise the renderer-to-raster wire format with nested paint records.
  alignas(16) std::array<uint8_t, 16384> wire{};
  cc::PaintOp::SerializeOptions serialize_options;
  cc::SimpleBufferSerializer serializer(wire.data(), wire.size(),
                                        serialize_options);
  serializer.Serialize(buffer);
  CHECK_CASE(serializer.valid() && serializer.written() > 0);
  std::vector<uint8_t> scratch;
  cc::PaintOpBuffer::DeserializeOptions options{.scratch_buffer = scratch};
  auto decoded = cc::PaintOpBuffer::MakeFromMemory(
      wire.data(), serializer.written(), options);
  CHECK_CASE(decoded && CheckPixels(*decoded) == 0);
  CHECK_CASE(!cc::PaintOpBuffer::MakeFromMemory(
      wire.data(), serializer.written() - 1, options));
  wire[0] = 0xff;
  CHECK_CASE(!cc::PaintOpBuffer::MakeFromMemory(wire.data(),
                                                serializer.written(), options));

  alignas(16) std::array<uint8_t, 8> tiny{};
  cc::SimpleBufferSerializer overflow(tiny.data(), tiny.size(),
                                      serialize_options);
  overflow.Serialize(buffer);
  CHECK_CASE(!overflow.valid());

  const gfx::ColorSpace srgb = gfx::ColorSpace::CreateSRGB();
  CHECK_CASE(srgb.IsValid() && !srgb.IsHDR());
  CHECK_CASE(srgb.ToSkColorSpace() && srgb.ToSkColorSpace()->isSRGB());
  CHECK_CASE(gfx::ColorSpace::CreateHDR10().IsHDR());

  // Retain the real Crashpad annotation provider used by paint diagnostics.
  crash_reporter::InitializeCrashKeys();
  static crash_reporter::CrashKeyString<32> key("bazel-paint-runtime");
  key.Set("paint-round-trip");
  CHECK_CASE(crash_reporter::GetCrashKeyValue("bazel-paint-runtime") ==
             "paint-round-trip");
  key.Clear();
  CHECK_CASE(crash_reporter::GetCrashKeyValue("bazel-paint-runtime").empty());
  return 0;
}
