#include <iostream>

#include "include/core/SkBitmap.h"
#include "include/core/SkCanvas.h"
#include "include/core/SkPaint.h"
#include "include/core/SkPath.h"
#include "include/pathops/SkPathOps.h"

int main() {
  SkBitmap bitmap;
  if (!bitmap.tryAllocN32Pixels(16, 16)) return 1;
  SkCanvas canvas(bitmap);
  canvas.clear(SK_ColorWHITE);
  SkPaint paint;
  paint.setColor(SK_ColorRED);
  canvas.drawRect(SkRect::MakeXYWH(4, 4, 8, 8), paint);
  if (bitmap.getColor(0, 0) != SK_ColorWHITE ||
      bitmap.getColor(8, 8) != SK_ColorRED) return 1;

  SkPath left = SkPath::Rect(SkRect::MakeXYWH(0, 0, 10, 10));
  SkPath right = SkPath::Rect(SkRect::MakeXYWH(5, 5, 10, 10));
  SkPath intersection;
  if (!Op(left, right, kIntersect_SkPathOp, &intersection) ||
      !intersection.contains(7, 7) || intersection.contains(2, 2)) return 1;
  std::cout << "Skia: raster pixels and path intersection passed\n";
  return 0;
}
