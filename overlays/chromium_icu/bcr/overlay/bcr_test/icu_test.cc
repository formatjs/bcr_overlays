#include <cstddef>
#include <fstream>
#include <iostream>
#include <memory>
#include <vector>

#include "unicode/brkiter.h"
#include "unicode/locid.h"
#include "unicode/normalizer2.h"
#include "unicode/numfmt.h"
#include "unicode/uclean.h"
#include "unicode/udata.h"
#include "unicode/uversion.h"

bool CheckBehavior() {
  UVersionInfo version;
  u_getVersion(version);
  if (version[0] != 74 || version[1] != 2) return false;

  UErrorCode status = U_ZERO_ERROR;
  const auto* normalizer = icu::Normalizer2::getNFCInstance(status);
  icu::UnicodeString normalized;
  if (U_FAILURE(status) || !normalizer) return false;
  normalizer->normalize(icu::UnicodeString::fromUTF8("e\xCC\x81"), normalized,
                        status);
  if (U_FAILURE(status) || normalized != icu::UnicodeString(u"\u00e9")) return false;

  status = U_ZERO_ERROR;
  std::unique_ptr<icu::NumberFormat> number(
      icu::NumberFormat::createInstance(icu::Locale("fr_FR"), status));
  if (U_FAILURE(status) || !number) return false;
  icu::UnicodeString formatted;
  number->format(1234.5, formatted);
  if (formatted.indexOf(u',') < 0) return false;

  status = U_ZERO_ERROR;
  std::unique_ptr<icu::BreakIterator> words(
      icu::BreakIterator::createWordInstance(icu::Locale::getEnglish(), status));
  if (U_FAILURE(status) || !words) return false;
  words->setText(icu::UnicodeString::fromUTF8("example.com"));
  words->first();
  std::vector<int32_t> boundaries;
  for (int32_t end = words->next(); end != icu::BreakIterator::DONE;
       end = words->next()) {
    boundaries.push_back(end);
  }
  return boundaries == std::vector<int32_t>({7, 8, 11});
}

int main(int argc, char** argv) {
  std::vector<std::max_align_t> data;
  UErrorCode status = U_ZERO_ERROR;
  if (argc == 2) {
    std::ifstream input(argv[1], std::ios::binary | std::ios::ate);
    if (!input) return 1;
    const auto bytes = input.tellg();
    if (bytes <= 0) return 1;
    data.resize((static_cast<size_t>(bytes) + sizeof(std::max_align_t) - 1) /
                sizeof(std::max_align_t));
    input.seekg(0);
    if (!input.read(reinterpret_cast<char*>(data.data()), bytes)) return 1;
    udata_setCommonData(data.data(), &status);
  }
  if (U_FAILURE(status)) return 1;
  u_init(&status);
  if (U_FAILURE(status)) {
    std::cerr << u_errorName(status) << '\n';
    return 1;
  }
  const bool passed = CheckBehavior();
  u_cleanup();
  if (!passed) return 1;
  std::cout << "Chromium ICU: NFC, locale formatting, patched word boundaries passed\n";
  return 0;
}
