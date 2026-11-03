#include <cstdint>
#include <cstring>
#include <string>
#include <string_view>

#include "base/third_party/cityhash/city.h"
#include "base/third_party/icu/icu_utf.h"
#include "build/build_config.h"
#include "double-conversion/double-conversion.h"
#include "gtest/gtest.h"
#include "tests/generated_buildflags.h"
#include "third_party/modp_b64/modp_b64.h"

static_assert(BUILDFLAG(ENABLED));
static_assert(!BUILDFLAG(DISABLED));
static_assert(BUILDFLAG(COUNT) == 7);
static_assert(std::string_view(BUILDFLAG(LABEL)) == "chromium");

TEST(Base64, Rfc4648Vectors) {
  const char* inputs[] = {"", "f", "fo", "foo", "foob", "fooba", "foobar"};
  const char* outputs[] = {"", "Zg==", "Zm8=", "Zm9v", "Zm9vYg==",
                           "Zm9vYmE=", "Zm9vYmFy"};
  for (int i = 0; i < 7; ++i) {
    SCOPED_TRACE(inputs[i]);
    const auto size = std::strlen(inputs[i]);
    std::string encoded(modp_b64_encode_len(size), '\0');
    encoded.resize(modp_b64_encode(encoded.data(), inputs[i], size));
    EXPECT_EQ(encoded, outputs[i]);
    std::string decoded(modp_b64_decode_len(encoded.size()), '\0');
    const auto written = modp_b64_decode(decoded.data(), encoded.data(), encoded.size());
    ASSERT_NE(written, MODP_B64_ERROR);
    decoded.resize(written);
    EXPECT_EQ(decoded, inputs[i]);
  }
}

TEST(Base64, RejectsInvalidPaddingAndAlphabet) {
  char output[32];
  for (const auto* input : {"Z", "Zg", "Zg=", "Zg===", "Zm$v", "Zm v"}) {
    EXPECT_EQ(modp_b64_decode(output, input, std::strlen(input)), MODP_B64_ERROR);
  }
  EXPECT_EQ(modp_b64_decode(output, "Zg", 2, ModpDecodePolicy::kForgiving), 1u);
  EXPECT_EQ(output[0], 'f');
}

TEST(Base64, PreservesBinaryBytes) {
  const char input[] = {'\0', static_cast<char>(0xff), static_cast<char>(0x80)};
  char encoded[modp_b64_encode_len(sizeof(input))];
  const auto size = modp_b64_encode(encoded, input, sizeof(input));
  char decoded[modp_b64_decode_len(sizeof(encoded))];
  ASSERT_EQ(modp_b64_decode(decoded, encoded, size), sizeof(input));
  EXPECT_EQ(std::memcmp(input, decoded, sizeof(input)), 0);
}

TEST(Utf8, HandlesSupplementaryCodePointAndRejectsOverlongEncoding) {
  const uint8_t text[] = {0xf0, 0x9f, 0x98, 0x80};
  int index = 0;
  int32_t code_point;
  CBU8_NEXT(text, index, 4, code_point);
  EXPECT_EQ(code_point, 0x1f600);
  EXPECT_EQ(index, 4);
  const uint8_t invalid[] = {0xc0, 0x80};
  index = 0;
  CBU8_NEXT(invalid, index, 2, code_point);
  EXPECT_EQ(code_point, CBU_SENTINEL);
}

TEST(CityHash, PreservesChromiumHashNamespaceAndSeedBehavior) {
  namespace city = base::internal::cityhash_v111;
  EXPECT_EQ(city::CityHash64("", 0), 0x9ae16a3b2f90404fULL);
  EXPECT_NE(city::CityHash64WithSeed("chromium", 8, 1),
            city::CityHash64WithSeed("chromium", 8, 2));
}

TEST(DoubleConversion, BcrLibraryRoundTripsShortestDecimal) {
  char buffer[32];
  double_conversion::StringBuilder builder(buffer, sizeof(buffer));
  ASSERT_TRUE(double_conversion::DoubleToStringConverter::EcmaScriptConverter()
                  .ToShortest(0.1, &builder));
  EXPECT_STREQ(builder.Finalize(), "0.1");
  double_conversion::StringToDoubleConverter parser(0, 0, -1, "Infinity", "NaN");
  int consumed = 0;
  EXPECT_EQ(parser.StringToDouble(buffer, 3, &consumed), 0.1);
  EXPECT_EQ(consumed, 3);
}
