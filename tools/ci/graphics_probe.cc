#include <fstream>
#include <iostream>

#include "third_party/skia/include/codec/SkCodec.h"
#include "third_party/skia/include/core/SkBitmap.h"
#include "third_party/skia/include/core/SkCanvas.h"
#include "third_party/skia/include/core/SkData.h"
#include "third_party/skia/include/core/SkGraphics.h"
#include "third_party/skia/include/core/SkPaint.h"
#include "third_party/skia/include/core/SkStream.h"
#include "third_party/skia/include/encode/SkPngRustEncoder.h"

namespace {
int Fail(const char* message) {
  std::cerr << message << '\n';
  return 1;
}
}  // namespace

int main(int argc, char** argv) {
  if (argc > 2) return Fail("Usage: graphics_probe [output.png]");
  SkGraphics::Init();
  SkBitmap bitmap;
  if (!bitmap.tryAllocN32Pixels(64, 48)) return Fail("Pixel allocation failed");
  SkCanvas canvas(bitmap);
  canvas.clear(SK_ColorWHITE);
  SkPaint paint;
  paint.setColor(SK_ColorRED);
  canvas.drawRect(SkRect::MakeXYWH(8, 8, 32, 24), paint);
  canvas.save();
  canvas.clipRect(SkRect::MakeXYWH(20, 4, 20, 32));
  paint.setColor(SK_ColorBLUE);
  canvas.drawCircle(32, 16, 8, paint);
  canvas.restore();
  paint.setColor(SkColorSetARGB(128, 0, 0, 0));
  canvas.drawRect(SkRect::MakeXYWH(0, 36, 64, 12), paint);

  SkPixmap pixels;
  if (!bitmap.peekPixels(&pixels)) return Fail("Raster pixels unavailable");
  SkDynamicMemoryWStream stream;
  if (!SkPngRustEncoder::Encode(&stream, pixels, {}))
    return Fail("Rust PNG encoding failed");
  auto encoded = stream.detachAsData();
  if (argc == 2) {
    std::ofstream output(argv[1], std::ios::binary);
    output.write(static_cast<const char*>(encoded->data()), encoded->size());
    if (!output) return Fail("PNG artifact write failed");
  }
  auto codec = SkCodec::MakeFromData(encoded);
  if (!codec) return Fail("PNG decoder unavailable");
  SkBitmap decoded;
  if (!decoded.tryAllocN32Pixels(64, 48) ||
      codec->getPixels(decoded.info(), decoded.getPixels(), decoded.rowBytes()) !=
          SkCodec::kSuccess)
    return Fail("PNG decoding failed");
  for (int y = 0; y < 48; ++y) {
    for (int x = 0; x < 64; ++x) {
      if (bitmap.getColor(x, y) != decoded.getColor(x, y))
        return Fail("PNG round-trip changed pixels");
    }
  }
  if (decoded.getColor(7, 7) != SK_ColorWHITE ||
      decoded.getColor(10, 10) != SK_ColorRED ||
      decoded.getColor(32, 16) != SK_ColorBLUE ||
      decoded.getColor(41, 16) != SK_ColorWHITE ||
      decoded.getColor(2, 40) != SkColorSetRGB(127, 127, 127))
    return Fail("Raster drawing or alpha blending failed");
  std::cout << "Skia raster, Rust PNG, 3072 matching pixels passed\n";
  return 0;
}
