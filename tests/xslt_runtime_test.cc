#include <cstdio>
#include <cstdlib>
#include <memory>
#include <string>
#include <string_view>

#include "base/at_exit.h"
#include "base/files/file.h"
#include "base/files/file_path.h"
#include "base/files/memory_mapped_file.h"
#include "base/i18n/icu_util.h"
#include "libxml/parser.h"
#include "libxml/tree.h"
#include "libxml/xmlversion.h"
#include "libxslt/transform.h"
#include "libxslt/xslt.h"
#include "libxslt/xsltutils.h"
#include "rules_cc/cc/runfiles/runfiles.h"

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

std::string Property(xmlNodePtr node, const char* name) {
  xmlChar* value = xmlGetProp(node, BAD_CAST name);
  if (!value) {
    return {};
  }
  std::string result(reinterpret_cast<const char*>(value));
  xmlFree(value);
  return result;
}

int main(int argc, char** argv) {
  base::AtExitManager at_exit;
  CHECK_CASE(argc == 2);
  std::string error;
  std::unique_ptr<rules_cc::cc::runfiles::Runfiles> runfiles(
      rules_cc::cc::runfiles::Runfiles::CreateForTest(&error));
  CHECK_CASE(runfiles);
  base::File data(base::FilePath(runfiles->Rlocation(argv[1])),
                  base::File::FLAG_OPEN | base::File::FLAG_READ);
  CHECK_CASE(data.IsValid());
  CHECK_CASE(base::i18n::InitializeICUWithFileDescriptor(
      data.TakePlatformFile(), base::MemoryMappedFile::Region::kWholeFile));
  CHECK_CASE(std::atoi(xmlParserVersion) == LIBXML_VERSION);
  CHECK_CASE(xsltLibxsltVersion == LIBXSLT_VERSION);

  constexpr std::string_view input =
      "<catalog><item id='one' price='7'/><item id='two' price='5'/></catalog>";
  constexpr std::string_view stylesheet = R"XSL(<xsl:stylesheet version="1.0"
      xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <xsl:output method="xml" omit-xml-declaration="yes"/>
    <xsl:param name="multiplier" select="2"/>
    <xsl:template match="/">
      <out total="{sum(catalog/item/@price) * $multiplier}">
        <xsl:for-each select="catalog/item">
          <xsl:variable name="attribute-id" select="generate-id(@id)"/>
          <xsl:variable name="temporary"><value><xsl:value-of select="@price"/></value></xsl:variable>
          <entry key="{@id}" stable="{$attribute-id = generate-id(@id)}"><xsl:value-of select="$temporary"/></entry>
        </xsl:for-each>
      </out>
    </xsl:template>
  </xsl:stylesheet>)XSL";
  xmlDocPtr style_doc = xmlReadMemory(stylesheet.data(), stylesheet.size(),
                                      "style.xsl", nullptr, XML_PARSE_NONET);
  CHECK_CASE(style_doc);
  xsltStylesheetPtr style = xsltParseStylesheetDoc(style_doc);
  CHECK_CASE(style);
  xmlDocPtr document = xmlReadMemory(input.data(), input.size(), "input.xml",
                                     nullptr, XML_PARSE_NONET);
  CHECK_CASE(document);
  const char* parameters[] = {"multiplier", "3", nullptr};
  for (int iteration = 0; iteration < 32; ++iteration) {
    xmlDocPtr output = xsltApplyStylesheet(style, document, parameters);
    CHECK_CASE(output);
    xmlNodePtr root = xmlDocGetRootElement(output);
    CHECK_CASE(root && xmlStrEqual(root->name, BAD_CAST "out"));
    CHECK_CASE(Property(root, "total") == "36");
    xmlNodePtr entry = xmlFirstElementChild(root);
    CHECK_CASE(entry && Property(entry, "key") == "one");
    CHECK_CASE(Property(entry, "stable") == "true");
    entry = xmlNextElementSibling(entry);
    CHECK_CASE(entry && Property(entry, "key") == "two");
    CHECK_CASE(Property(entry, "stable") == "true");
    CHECK_CASE(!xmlNextElementSibling(entry));
    xmlChar* bytes = nullptr;
    int length = 0;
    CHECK_CASE(xsltSaveResultToString(&bytes, &length, output, style) >= 0);
    CHECK_CASE(bytes && length > 0);
    const std::string serialized(reinterpret_cast<const char*>(bytes), length);
    CHECK_CASE(serialized.find(">7</entry>") != std::string::npos);
    CHECK_CASE(serialized.find(">5</entry>") != std::string::npos);
    xmlFree(bytes);
    xmlFreeDoc(output);
  }
  xmlFreeDoc(document);
  xsltFreeStylesheet(style);
  std::puts(
      "BCR libxslt/Chromium libxml: parameters, XPath, attribute IDs, "
      "temporary trees and repeated transformation passed");
  return 0;
}
