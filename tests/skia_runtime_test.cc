#include <sys/resource.h>
#include <sys/wait.h>
#include <unistd.h>
#include <cmath>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <string>

#include "base/at_exit.h"
#include "base/files/file.h"
#include "base/files/memory_mapped_file.h"
#include "base/i18n/icu_util.h"
#include "include/codec/SkCodec.h"
#include "include/codec/SkPngDecoder.h"
#include "include/codec/SkPngRustDecoder.h"
#include "include/core/SkBitmap.h"
#include "include/core/SkCanvas.h"
#include "include/core/SkData.h"
#include "include/core/SkFont.h"
#include "include/core/SkGraphics.h"
#include "include/core/SkPaint.h"
#include "include/core/SkPath.h"
#include "include/core/SkStream.h"
#include "include/docs/SkPDFDocument.h"
#include "include/encode/SkPngRustEncoder.h"
#include "include/ports/SkTypeface_fontations.h"
#include "partition_alloc/partition_alloc.h"
#include "rules_cc/cc/runfiles/runfiles.h"

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

int CheckRendering(const std::string& font_path) {
  auto data = SkData::MakeFromFileName(font_path.c_str());
  CHECK_CASE(data);
  auto typeface = SkTypeface_Make_Fontations(data, SkFontArguments());
  CHECK_CASE(typeface);
  CHECK_CASE(!SkTypeface_Make_Fontations(SkData::MakeWithCopy("invalid", 7),
                                         SkFontArguments()));
  SkFont font(typeface, 20);
  CHECK_CASE(std::abs(font.measureText("A", 1, SkTextEncoding::kUTF8) - 20) <
             0.0001);
  const SkGlyphID glyph = typeface->unicharToGlyph('A');
  CHECK_CASE(glyph != 0);
  auto path = font.getPath(glyph);
  CHECK_CASE(path);
  CHECK_CASE(std::abs(path->getBounds().width() - 20) < 0.0001);
  CHECK_CASE(std::abs(path->getBounds().height() - 20) < 0.0001);

  SkBitmap bitmap;
  CHECK_CASE(bitmap.tryAllocPixels(SkImageInfo::MakeN32Premul(32, 32)));
  SkCanvas canvas(bitmap);
  canvas.clear(SK_ColorWHITE);
  SkPaint paint;
  paint.setColor(SK_ColorBLACK);
  canvas.drawSimpleText("A", 1, SkTextEncoding::kUTF8, 4, 22, font, paint);
  CHECK_CASE(bitmap.getColor(12, 12) == SK_ColorBLACK);
  CHECK_CASE(bitmap.getColor(0, 0) == SK_ColorWHITE);

  // Rust encoding crosses the real CXX bridge; both decoders must agree.
  SkDynamicMemoryWStream png_stream;
  CHECK_CASE(SkPngRustEncoder::Encode(&png_stream, bitmap.pixmap(), {}));
  auto encoded = png_stream.detachAsData();
  CHECK_CASE(encoded && encoded->size() > 8);
  CHECK_CASE(std::memcmp(encoded->data(), "\x89PNG\r\n\x1a\n", 8) == 0);
  for (bool rust : {false, true}) {
    SkCodec::Result result;
    auto stream = std::make_unique<SkMemoryStream>(encoded);
    auto codec = rust ? SkPngRustDecoder::Decode(std::move(stream), &result)
                      : SkPngDecoder::Decode(std::move(stream), &result);
    CHECK_CASE(codec && result == SkCodec::kSuccess);
    CHECK_CASE(codec->dimensions() == SkISize::Make(32, 32));
    SkBitmap decoded;
    CHECK_CASE(decoded.tryAllocPixels(SkImageInfo::MakeN32Premul(32, 32)));
    CHECK_CASE(codec->getPixels(decoded.info(), decoded.getPixels(),
                                decoded.rowBytes()) == SkCodec::kSuccess);
    for (int y = 0; y < 32; ++y) {
      for (int x = 0; x < 32; ++x) {
        CHECK_CASE(decoded.getColor(x, y) == bitmap.getColor(x, y));
      }
    }
    auto truncated = std::make_unique<SkMemoryStream>(encoded->data(), 8, true);
    auto rejected =
        rust ? SkPngRustDecoder::Decode(std::move(truncated), &result)
             : SkPngDecoder::Decode(std::move(truncated), &result);
    CHECK_CASE(!rejected);
  }

  SkDynamicMemoryWStream pdf;
  auto document = SkPDF::MakeDocument(&pdf);
  CHECK_CASE(document);
  SkCanvas* page = document->beginPage(64, 64);
  CHECK_CASE(page);
  page->drawSimpleText("A", 1, SkTextEncoding::kUTF8, 4, 22, font, paint);
  document->endPage();
  document->close();
  auto pdf_data = pdf.detachAsData();
  CHECK_CASE(pdf_data && pdf_data->size() > 1000);
  const std::string pdf_bytes(static_cast<const char*>(pdf_data->data()),
                              pdf_data->size());
  CHECK_CASE(pdf_bytes.starts_with("%PDF-"));
  CHECK_CASE(pdf_bytes.find("/Type /Font") != std::string::npos);
  CHECK_CASE(pdf_bytes.find("%%EOF") != std::string::npos);
  return 0;
}

int main(int argc, char** argv) {
  partition_alloc::PartitionAllocGlobalInit([](size_t) { std::abort(); });
  base::AtExitManager at_exit;
  CHECK_CASE(argc == 3);
  std::string error;
  std::unique_ptr<rules_cc::cc::runfiles::Runfiles> runfiles(
      rules_cc::cc::runfiles::Runfiles::CreateForTest(&error));
  CHECK_CASE(runfiles);
  base::File data(base::FilePath(runfiles->Rlocation(argv[1])),
                  base::File::FLAG_OPEN | base::File::FLAG_READ);
  CHECK_CASE(data.IsValid());
  CHECK_CASE(base::i18n::InitializeICUWithFileDescriptor(
      data.TakePlatformFile(), base::MemoryMappedFile::Region::kWholeFile));
  SkGraphics::Init();
  CHECK_CASE(CheckRendering(runfiles->Rlocation(argv[2])) == 0);
  const pid_t child = fork();
  CHECK_CASE(child >= 0);
  if (child == 0) {
    const rlimit limit{0, 0};
    setrlimit(RLIMIT_CORE, &limit);
    SkASSERT(false);
    _exit(0);
  }
  int status = 0;
  CHECK_CASE(waitpid(child, &status, 0) == child);
  CHECK_CASE(WIFSIGNALED(status));
  CHECK_CASE(WTERMSIG(status) == SIGTRAP || WTERMSIG(status) == SIGILL ||
             WTERMSIG(status) == SIGABRT);
  return 0;
}
