#include <expat.h>
#include <string.h>

static void XMLCALL element(void *data, const XML_Char *name,
                            const XML_Char **attributes) {
  (void)attributes;
  if (strcmp(name, "page") == 0) ++*(unsigned *)data;
}

int main(void) {
  const char document[] = "<page><text>Chromium</text></page>";
  unsigned pages = 0;
  XML_Parser parser = XML_ParserCreate("UTF-8");
  if (!parser) return 1;
  XML_SetUserData(parser, &pages);
  XML_SetStartElementHandler(parser, element);
  int valid = XML_Parse(parser, document, sizeof(document) - 1, XML_TRUE);
  if (valid != XML_STATUS_OK || pages != 1) {
    XML_ParserFree(parser);
    return 2;
  }
  XML_ParserReset(parser, NULL);
  int invalid = XML_Parse(parser, "<page>", 6, XML_TRUE);
  XML_ParserFree(parser);
  return invalid == XML_STATUS_ERROR ? 0 : 3;
}
