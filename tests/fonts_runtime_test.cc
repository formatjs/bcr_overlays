#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <string>
#include <vector>

#include "base/at_exit.h"
#include "base/files/file.h"
#include "base/files/memory_mapped_file.h"
#include "base/i18n/icu_util.h"
#include "fontconfig/fontconfig.h"
#include "ft2build.h"
#include FT_FREETYPE_H
#include "hb-icu.h"
#include "hb-ot.h"
#include "hb.h"
#include "libxml/parser.h"
#include "libxml/tree.h"
#include "partition_alloc/partition_alloc.h"
#include "png.h"
#include "rules_cc/cc/runfiles/runfiles.h"
#include "uuid/uuid.h"
#include "zlib.h"

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

int CheckFonts(const std::string& path) {
  FT_Library library = nullptr;
  CHECK_CASE(FT_Init_FreeType(&library) == 0);
  FT_Face face = nullptr;
  CHECK_CASE(FT_New_Face(library, path.c_str(), 0, &face) == 0);
  CHECK_CASE(FT_Set_Pixel_Sizes(face, 0, 20) == 0);
  const FT_UInt glyph = FT_Get_Char_Index(face, 'A');
  CHECK_CASE(glyph != 0);
  CHECK_CASE(FT_Load_Glyph(face, glyph, FT_LOAD_DEFAULT) == 0);
  CHECK_CASE(face->glyph->advance.x == 20 * 64);
  CHECK_CASE(FT_Render_Glyph(face->glyph, FT_RENDER_MODE_NORMAL) == 0);
  CHECK_CASE(face->glyph->bitmap.width == 20 && face->glyph->bitmap.rows == 20);
  CHECK_CASE(face->glyph->bitmap.buffer[10 * face->glyph->bitmap.pitch + 10] ==
             255);
  FT_Face invalid_face = nullptr;
  const FT_Byte bad_font[] = {0, 1, 0, 0, 0, 11, 0, 0, 0, 0, 0, 0};
  CHECK_CASE(FT_New_Memory_Face(library, bad_font, sizeof(bad_font), 0,
                                &invalid_face) != 0);

  hb_blob_t* blob = hb_blob_create_from_file_or_fail(path.c_str());
  CHECK_CASE(blob);
  hb_face_t* hb_face = hb_face_create(blob, 0);
  hb_font_t* font = hb_font_create(hb_face);
  hb_ot_font_set_funcs(font);
  hb_font_set_scale(font, 20 * 64, 20 * 64);
  hb_unicode_funcs_t* unicode = hb_icu_get_unicode_funcs();
  CHECK_CASE(hb_unicode_script(unicode, 0x0627) == HB_SCRIPT_ARABIC);
  CHECK_CASE(hb_unicode_combining_class(unicode, 0x0301) == 230);
  for (bool rtl : {false, true}) {
    hb_buffer_t* buffer = hb_buffer_create();
    hb_buffer_set_unicode_funcs(buffer, unicode);
    hb_buffer_add_utf8(buffer, "AB A", 4, 0, 4);
    hb_buffer_set_direction(buffer, rtl ? HB_DIRECTION_RTL : HB_DIRECTION_LTR);
    hb_buffer_guess_segment_properties(buffer);
    hb_shape(font, buffer, nullptr, 0);
    unsigned count = 0;
    const auto* info = hb_buffer_get_glyph_infos(buffer, &count);
    const auto* positions = hb_buffer_get_glyph_positions(buffer, nullptr);
    CHECK_CASE(count == 4);
    for (unsigned i = 0; i < count; ++i) {
      CHECK_CASE(info[i].cluster == (rtl ? 3 - i : i));
      CHECK_CASE(positions[i].x_advance == 20 * 64);
      CHECK_CASE(positions[i].y_advance == 0);
    }
    CHECK_CASE(info[rtl ? 3 : 0].codepoint == glyph);
    hb_buffer_destroy(buffer);
  }
  hb_font_destroy(font);
  hb_face_destroy(hb_face);
  hb_blob_destroy(blob);
  CHECK_CASE(FT_Done_Face(face) == 0);
  CHECK_CASE(FT_Done_FreeType(library) == 0);

  constexpr char configuration[] = R"(
    <fontconfig><match target="pattern">
      <test name="family"><string>AliasAhem</string></test>
      <edit name="family" mode="assign"><string>Ahem</string></edit>
    </match></fontconfig>)";
  const std::string invalid_path =
      std::string(std::getenv("TEST_TMPDIR")) + "/invalid.ttf";
  FILE* invalid = std::fopen(invalid_path.c_str(), "wb");
  CHECK_CASE(invalid);
  CHECK_CASE(std::fwrite(bad_font, 1, sizeof(bad_font), invalid) ==
             sizeof(bad_font));
  CHECK_CASE(std::fclose(invalid) == 0);
  for (bool fontations : {false, true}) {
    if (fontations) {
      CHECK_CASE(setenv("FC_FONTATIONS", "1", 1) == 0);
    } else {
      CHECK_CASE(unsetenv("FC_FONTATIONS") == 0);
    }
    FcConfig* config = FcConfigCreate();
    CHECK_CASE(config);
    CHECK_CASE(FcConfigParseAndLoadFromMemory(
        config, reinterpret_cast<const FcChar8*>(configuration), FcTrue));
    CHECK_CASE(FcConfigAppFontAddFile(
        config, reinterpret_cast<const FcChar8*>(path.c_str())));
    CHECK_CASE(!FcConfigAppFontAddFile(
        config, reinterpret_cast<const FcChar8*>(invalid_path.c_str())));
    FcPattern* pattern = FcPatternCreate();
    CHECK_CASE(FcPatternAddString(
        pattern, FC_FAMILY, reinterpret_cast<const FcChar8*>("AliasAhem")));
    CHECK_CASE(FcConfigSubstitute(config, pattern, FcMatchPattern));
    FcDefaultSubstitute(pattern);
    FcResult result;
    FcPattern* match = FcFontMatch(config, pattern, &result);
    CHECK_CASE(match && result == FcResultMatch);
    FcChar8* family = nullptr;
    CHECK_CASE(FcPatternGetString(match, FC_FAMILY, 0, &family) ==
               FcResultMatch);
    CHECK_CASE(std::strcmp(reinterpret_cast<const char*>(family), "Ahem") == 0);
    FcCharSet* charset = nullptr;
    CHECK_CASE(FcPatternGetCharSet(match, FC_CHARSET, 0, &charset) ==
               FcResultMatch);
    CHECK_CASE(FcCharSetHasChar(charset, 'A'));
    CHECK_CASE(!FcCharSetHasChar(charset, 0x4e00));
    FcPatternDestroy(match);
    FcPatternDestroy(pattern);
    FcConfigDestroy(config);
  }
  unsetenv("FC_FONTATIONS");
  FcFini();
  return 0;
}

struct PngInput {
  const unsigned char* data;
  size_t size;
  size_t offset;
};

void ReadPng(png_structp decoder, png_bytep destination, size_t size) {
  auto* input = static_cast<PngInput*>(png_get_io_ptr(decoder));
  if (size > input->size - input->offset) {
    png_error(decoder, "truncated input");
  }
  std::memcpy(destination, input->data + input->offset, size);
  input->offset += size;
}

int CheckTextLimit(const std::array<unsigned char, 75>& image) {
  for (uint32_t text_length : {32u, 4000002u}) {
    std::vector<unsigned char> text_data(text_length, 'a');
    uLongf compressed_length = compressBound(text_length);
    std::vector<unsigned char> compressed(compressed_length);
    CHECK_CASE(compress2(compressed.data(), &compressed_length,
                         text_data.data(), text_length,
                         Z_DEFAULT_COMPRESSION) == Z_OK);
    const uint32_t length = compressed_length + 3;
    std::vector<unsigned char> chunk(12 + length);
    for (int i = 0; i < 4; ++i)
      chunk[i] = length >> (24 - 8 * i);
    std::memcpy(chunk.data() + 4, "zTXt", 4);
    chunk[8] = 'k';
    chunk[9] = 0;
    chunk[10] = 0;
    std::memcpy(chunk.data() + 11, compressed.data(), compressed_length);
    const uint32_t crc = crc32(0, chunk.data() + 4, length + 4);
    for (int i = 0; i < 4; ++i)
      chunk[8 + length + i] = crc >> (24 - 8 * i);
    std::vector<unsigned char> input(image.begin(), image.begin() + 33);
    input.insert(input.end(), chunk.begin(), chunk.end());
    input.insert(input.end(), image.begin() + 33, image.end());
    PngInput stream{input.data(), input.size(), 0};
    png_structp decoder = png_create_read_struct(PNG_LIBPNG_VER_STRING, nullptr,
                                                 nullptr, nullptr);
    CHECK_CASE(decoder);
    png_infop info = png_create_info_struct(decoder);
    CHECK_CASE(info);
    if (setjmp(png_jmpbuf(decoder))) {
      png_destroy_read_struct(&decoder, &info, nullptr);
      return 1;
    }
    png_set_read_fn(decoder, &stream, ReadPng);
    png_read_info(decoder, info);
    png_textp text = nullptr;
    CHECK_CASE(png_get_text(decoder, info, &text, nullptr) ==
               (text_length == 32 ? 1 : 0));
    png_destroy_read_struct(&decoder, &info, nullptr);
  }
  return 0;
}

int CheckImagesAndXml() {
  constexpr std::array<unsigned char, 75> image = {
      137, 80,  78,  71, 13,  10, 26, 10, 0,   0,  0,  13,  73, 72,  68,
      82,  0,   0,   0,  2,   0,  0,  0,  1,   8,  2,  0,   0,  0,   123,
      64,  232, 221, 0,  0,   0,  18, 73, 68,  65, 84, 120, 1,  1,   7,
      0,   248, 255, 0,  255, 0,  0,  0,  255, 0,  7,  255, 1,  255, 197,
      14,  226, 106, 0,  0,   0,  0,  73, 69,  78, 68, 174, 66, 96,  130};
  png_image decoder{};
  decoder.version = PNG_IMAGE_VERSION;
  CHECK_CASE(
      png_image_begin_read_from_memory(&decoder, image.data(), image.size()));
  CHECK_CASE(decoder.width == 2 && decoder.height == 1);
  decoder.format = PNG_FORMAT_RGB;
  std::array<unsigned char, 6> pixels{};
  CHECK_CASE(
      png_image_finish_read(&decoder, nullptr, pixels.data(), 0, nullptr));
  CHECK_CASE((pixels == std::array<unsigned char, 6>{255, 0, 0, 0, 255, 0}));
  png_image_free(&decoder);
  CHECK_CASE(CheckTextLimit(image) == 0);
  auto oversized = image;
  const uint32_t width = 1000001;
  for (int i = 0; i < 4; ++i)
    oversized[16 + i] = width >> (24 - 8 * i);
  const uint32_t crc = crc32(0, oversized.data() + 12, 17);
  for (int i = 0; i < 4; ++i)
    oversized[29 + i] = crc >> (24 - 8 * i);
  decoder = {};
  decoder.version = PNG_IMAGE_VERSION;
  CHECK_CASE(!png_image_begin_read_from_memory(&decoder, oversized.data(),
                                               oversized.size()));
  png_image_free(&decoder);

  constexpr char xml[] = "<root label='caf&#233;'><child/></root>";
  xmlDocPtr document =
      xmlReadMemory(xml, sizeof(xml) - 1, nullptr, nullptr, XML_PARSE_NONET);
  CHECK_CASE(document);
  xmlNodePtr root = xmlDocGetRootElement(document);
  xmlChar* label = xmlGetProp(root, reinterpret_cast<const xmlChar*>("label"));
  CHECK_CASE(label && std::strcmp(reinterpret_cast<const char*>(label),
                                  "caf\xc3\xa9") == 0);
  xmlFree(label);
  xmlFreeDoc(document);
  constexpr char malformed[] = "<root><child></root>";
  CHECK_CASE(!xmlReadMemory(
      malformed, sizeof(malformed) - 1, nullptr, nullptr,
      XML_PARSE_NONET | XML_PARSE_NOERROR | XML_PARSE_NOWARNING));

  uuid_t id;
  uuid_t parsed;
  uuid_generate_random(id);
  CHECK_CASE(uuid_type(id) == 4 && uuid_variant(id) == UUID_VARIANT_DCE);
  char text[37];
  uuid_unparse_lower(id, text);
  CHECK_CASE(uuid_parse(text, parsed) == 0 && uuid_compare(id, parsed) == 0);
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
  CHECK_CASE(CheckFonts(runfiles->Rlocation(argv[2])) == 0);
  CHECK_CASE(CheckImagesAndXml() == 0);
  return 0;
}
