#include <cstdio>
#include <memory>
#include <string>
#include <string_view>

#include "base/at_exit.h"
#include "base/command_line.h"
#include "base/debug/stack_trace.h"
#include "base/feature_list.h"
#include "base/files/file.h"
#include "base/files/file_path.h"
#include "base/files/memory_mapped_file.h"
#include "base/i18n/icu_util.h"
#include "base/no_destructor.h"
#include "rules_cc/cc/runfiles/runfiles.h"
#include "third_party/blink/public/platform/platform.h"
#include "third_party/blink/public/platform/web_string.h"
#include "third_party/blink/renderer/platform/graphics/color.h"
#include "third_party/blink/renderer/platform/language.h"
#include "third_party/blink/renderer/platform/text/character.h"
#include "third_party/blink/renderer/platform/text/character_break_iterator.h"
#include "third_party/blink/renderer/platform/wtf/allocator/partitions.h"
#include "third_party/blink/renderer/platform/wtf/text/atomic_string.h"
#include "third_party/blink/renderer/platform/wtf/text/wtf_string.h"
#include "third_party/blink/renderer/platform/wtf/wtf.h"

namespace {
class TestPlatform final : public blink::Platform {
 public:
  blink::WebString DefaultLocale() override {
    return blink::WebString::FromUTF8("en-US");
  }
};
}  // namespace

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

int main(int argc, char** argv) {
  base::debug::EnableInProcessStackDumping();
  base::AtExitManager at_exit;
  base::CommandLine::Init(argc, argv);
  CHECK_CASE(argc == 2);
  CHECK_CASE(base::FeatureList::InitInstance("", ""));
  std::string error;
  std::unique_ptr<rules_cc::cc::runfiles::Runfiles> runfiles(
      rules_cc::cc::runfiles::Runfiles::CreateForTest(&error));
  CHECK_CASE(runfiles);
  base::File data(base::FilePath(runfiles->Rlocation(argv[1])),
                  base::File::FLAG_OPEN | base::File::FLAG_READ);
  CHECK_CASE(data.IsValid());
  CHECK_CASE(base::i18n::InitializeICUWithFileDescriptor(
      data.TakePlatformFile(), base::MemoryMappedFile::Region::kWholeFile));
  static base::NoDestructor<TestPlatform> platform;
  blink::Platform::SetCurrentPlatformForTesting(platform.get());
  blink::Partitions::Initialize();
  blink::InitializeWtf();
  blink::InitializePlatformLanguage();

  const std::string utf8 =
      "Ae\u0301\U0001F469\u200D\U0001F4BB\U0001F1FA\U0001F1F3Z";
  const blink::String text = blink::String::FromUTF8(utf8);
  CHECK_CASE(text.length() == 13);
  CHECK_CASE(text.Utf8() == utf8);
  CHECK_CASE(blink::String::FromUTF8(std::string_view("\xc0\xaf", 2)).IsNull());
  CHECK_CASE(blink::NumGraphemeClusters(text) == 5);
  blink::CharacterBreakIterator clusters(text);
  for (int boundary : {1, 3, 8, 12, 13}) {
    CHECK_CASE(clusters.Next() == boundary);
  }
  CHECK_CASE(clusters.Next() == blink::kTextBreakDone);
  CHECK_CASE(!clusters.IsBreak(2));
  CHECK_CASE(!clusters.IsBreak(5));
  CHECK_CASE(clusters.Preceding(12) == 8);
  CHECK_CASE(clusters.Following(3) == 8);
  const blink::String ascii("A\r\nB");
  CHECK_CASE(ascii.Is8Bit());
  CHECK_CASE(blink::NumGraphemeClusters(ascii) == 3);
  blink::CharacterBreakIterator ascii_clusters(ascii);
  for (int boundary : {1, 3, 4}) {
    CHECK_CASE(ascii_clusters.Next() == boundary);
  }
  CHECK_CASE(ascii_clusters.Next() == blink::kTextBreakDone);
  const blink::AtomicString interned(text);
  const blink::AtomicString same(blink::String::FromUTF8(utf8));
  CHECK_CASE(interned.Impl() == same.Impl());

  CHECK_CASE(blink::Character::IsCJKIdeographOrSymbol(0x4e00));
  CHECK_CASE(!blink::Character::IsCJKIdeographOrSymbol('A'));
  CHECK_CASE(blink::Character::IsEmoji(0x1f469));
  CHECK_CASE(!blink::Character::IsEmoji('A'));
  CHECK_CASE(blink::Character::MaybeBidiRtl(0x0627));
  CHECK_CASE(!blink::Character::MaybeBidiRtl('A'));

  const auto* red = blink::FindColor("red");
  CHECK_CASE(red && red->argb_value == 0xffff0000u);
  CHECK_CASE(!blink::FindColor("unknown-color"));
  blink::Color purple;
  CHECK_CASE(purple.SetNamedColor(blink::String("ReBeCcApUrPlE")));
  CHECK_CASE(purple.Rgb() == 0xff663399u);
  CHECK_CASE(!purple.SetNamedColor(blink::String("unknown-color")));
  std::puts(
      "Blink platform: UTF-8, grapheme boundaries, interning, Unicode "
      "properties and generated CSS color lookup passed");
  return 0;
}
