#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>

#include "base/at_exit.h"
#include "mojo/core/embedder/embedder.h"
#include "partition_alloc/partition_alloc.h"
#include "ui/gfx/geometry/mojom/geometry.mojom-shared-internal.h"
#include "ui/gfx/geometry/mojom/geometry.mojom.h"
#include "ui/gfx/geometry/point_f.h"
#include "ui/gfx/geometry/rect.h"
#include "ui/gfx/geometry/rrect_f.h"
#include "ui/gfx/geometry/size.h"
#include "ui/gfx/geometry/skia_conversions.h"
#include "ui/gfx/geometry/transform.h"
#include "ui/gfx/range/mojom/range.mojom.h"
#include "ui/gfx/range/range.h"

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

bool Near(const gfx::PointF& a, const gfx::PointF& b) {
  return std::abs(a.x() - b.x()) < 0.0001f && std::abs(a.y() - b.y()) < 0.0001f;
}

int main() {
  partition_alloc::PartitionAllocGlobalInit([](size_t) { std::abort(); });
  base::AtExitManager at_exit;
  mojo::core::Init();
  gfx::Rect rectangle(-5, -2, 10, 8);
  rectangle.Intersect(gfx::Rect(0, 0, 9, 9));
  CHECK_CASE(rectangle == gfx::Rect(0, 0, 5, 6));
  CHECK_CASE(rectangle.Contains(gfx::Point(0, 0)));
  CHECK_CASE(!rectangle.Contains(gfx::Point(5, 6)));
  CHECK_CASE(gfx::ScaleToEnclosingRect(gfx::Rect(-3, 2, 7, 4), 1.5f) ==
             gfx::Rect(-5, 3, 11, 6));

  gfx::Transform translation;
  translation.Translate(10, 20);
  CHECK_CASE(
      Near(translation.MapPoint(gfx::PointF(2, 3)), gfx::PointF(12, 23)));
  gfx::Transform inverse;
  CHECK_CASE(translation.GetInverse(&inverse));
  CHECK_CASE(Near(inverse.MapPoint(translation.MapPoint(gfx::PointF(2, 3))),
                  gfx::PointF(2, 3)));
  gfx::Transform rotation;
  rotation.RotateAboutZAxis(90);
  CHECK_CASE(Near(rotation.MapPoint(gfx::PointF(2, 1)), gfx::PointF(-1, 2)));
  CHECK_CASE(!gfx::Transform::MakeScale(0).GetInverse(&inverse));

  const SkMatrix skia_matrix = gfx::TransformToFlattenedSkMatrix(translation);
  SkPoint mapped{2, 3};
  skia_matrix.mapPoints(SkSpan<SkPoint>(&mapped, 1));
  CHECK_CASE(Near(gfx::SkPointToPointF(mapped), gfx::PointF(12, 23)));
  const gfx::RRectF rounded(gfx::RectF(0, 0, 20, 10), 4);
  CHECK_CASE(rounded.Contains(gfx::RectF(5, 2, 10, 6)));
  CHECK_CASE(!rounded.Contains(gfx::RectF(0, 0, 1, 1)));

  gfx::Range reversed(9, 2);
  CHECK_CASE(reversed.is_reversed() && reversed.length() == 7);
  CHECK_CASE(reversed.Contains(gfx::Range(3, 5)));
  CHECK_CASE(reversed.Intersect(gfx::Range(0, 4)) == gfx::Range(2, 4));
  CHECK_CASE(!reversed.Intersect(gfx::Range(20, 30)).IsValid());

  auto rect_bytes = gfx::mojom::Rect::Serialize(&rectangle);
  gfx::Rect decoded_rect;
  CHECK_CASE(gfx::mojom::Rect::Deserialize(rect_bytes, &decoded_rect));
  CHECK_CASE(decoded_rect == rectangle);
  CHECK_CASE(
      !gfx::mojom::Rect::Deserialize(rect_bytes.data(), 4, &decoded_rect));
  auto range_bytes = gfx::mojom::Range::Serialize(&reversed);
  gfx::Range decoded_range;
  CHECK_CASE(gfx::mojom::Range::Deserialize(range_bytes, &decoded_range));
  CHECK_CASE(decoded_range == reversed && decoded_range.is_reversed());
  auto invalid = gfx::Range::InvalidRange();
  auto invalid_bytes = gfx::mojom::Range::Serialize(&invalid);
  CHECK_CASE(gfx::mojom::Range::Deserialize(invalid_bytes, &decoded_range));
  CHECK_CASE(!decoded_range.IsValid());

  // A negative wire size must fail rather than being clamped by gfx::Size.
  gfx::Size size(12345, 6);
  auto size_bytes = gfx::mojom::Size::Serialize(&size);
  constexpr size_t width_offset =
      offsetof(gfx::mojom::internal::Size_Data, width);
  CHECK_CASE(size_bytes.size() >= width_offset + sizeof(int32_t));
  int32_t encoded_width = 0;
  std::memcpy(&encoded_width, size_bytes.data() + width_offset,
              sizeof(encoded_width));
  CHECK_CASE(encoded_width == size.width());
  const int32_t negative = -1;
  std::memcpy(size_bytes.data() + width_offset, &negative, sizeof(negative));
  gfx::Size decoded_size;
  CHECK_CASE(!gfx::mojom::Size::Deserialize(size_bytes, &decoded_size));
  return 0;
}
