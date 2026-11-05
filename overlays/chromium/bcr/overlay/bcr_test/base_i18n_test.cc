#include <array>
#include <cstdio>
#include <cstdlib>
#include <memory>
#include <string>
#include <vector>

#include "base/at_exit.h"
#include "base/files/file.h"
#include "base/files/memory_mapped_file.h"
#include "base/i18n/break_iterator.h"
#include "base/i18n/case_conversion.h"
#include "base/i18n/encoding_detection.h"
#include "base/i18n/icu_string_conversions.h"
#include "base/i18n/icu_util.h"
#include "base/i18n/number_formatting.h"
#include "base/i18n/rtl.h"
#include "base/i18n/streaming_utf8_validator.h"
#include "base/i18n/transliterator.h"
#include "partition_alloc/partition_alloc.h"
#include "rules_cc/cc/runfiles/runfiles.h"

int main(int argc, char** argv) {
  partition_alloc::PartitionAllocGlobalInit([](size_t) { std::abort(); });
  base::AtExitManager at_exit;
  if (argc != 2) return 1;
  std::string error;
  std::unique_ptr<rules_cc::cc::runfiles::Runfiles> runfiles(
      rules_cc::cc::runfiles::Runfiles::CreateForTest(&error));
  if (!runfiles) {
    std::fprintf(stderr, "%s\n", error.c_str());
    return 1;
  }
  const auto data_path = runfiles->Rlocation(argv[1]);
  base::File data(base::FilePath(data_path), base::File::FLAG_OPEN | base::File::FLAG_READ);
  if (!data.IsValid() || !base::i18n::InitializeICUWithFileDescriptor(
      data.TakePlatformFile(), base::MemoryMappedFile::Region::kWholeFile)) return 2;
  base::i18n::SetICUDefaultLocale("fr_FR");
  if (base::FormatDouble(1234.5, 1) != u"1\u202f234,5") return 3;
  if (base::i18n::ToLower(u"\u00c4BC") != u"\u00e4bc") return 4;
  {
    const std::u16string text = u"example.com";
    base::i18n::BreakIterator words(text, base::i18n::BreakIterator::BREAK_WORD);
    if (!words.Init()) return 5;
    std::vector<std::u16string> segments;
    while (words.Advance()) segments.emplace_back(words.GetString());
    if (segments != std::vector<std::u16string>{u"example", u".", u"com"}) return 6;
    auto transform = base::i18n::CreateTransliterator("NFD; [:Nonspacing Mark:] Remove; NFC");
    if (!transform || transform->Transliterate(u"Caf\u00e9") != u"Cafe") return 7;
  }
  std::string encoding;
  if (!base::DetectEncoding("\xe6\x97\xa5\xe6\x9c\xac\xe8\xaa\x9e \xe6\x97\xa5\xe6\x9c\xac\xe8\xaa\x9e", &encoding) ||
      encoding != "UTF-8") return 8;
  std::u16string converted;
  if (!base::CodepageToUTF16("caf\xe9", "windows-1252", base::OnStringConversionError::FAIL, &converted) ||
      converted != u"caf\u00e9") return 9;
  if (base::CodepageToUTF16("\xc0\xaf", "UTF-8", base::OnStringConversionError::FAIL, &converted)) return 10;
  base::StreamingUtf8Validator validator;
  const std::array<uint8_t, 2> first = {0xf0, 0x9f};
  const std::array<uint8_t, 2> second = {0x8c, 0x8d};
  const std::array<uint8_t, 3> surrogate = {0xed, 0xa0, 0x80};
  if (validator.AddBytes(first) != base::StreamingUtf8Validator::VALID_MIDPOINT ||
      validator.AddBytes(second) != base::StreamingUtf8Validator::VALID_ENDPOINT ||
      validator.AddBytes(surrogate) != base::StreamingUtf8Validator::INVALID ||
      validator.AddBytes(second) != base::StreamingUtf8Validator::INVALID) return 11;
  validator.Reset();
  const std::array<uint8_t, 1> ascii = {'A'};
  if (validator.AddBytes(ascii) != base::StreamingUtf8Validator::VALID_ENDPOINT ||
      base::StreamingUtf8Validator::Validate("\xc0\xaf")) return 12;
  return 0;
}
