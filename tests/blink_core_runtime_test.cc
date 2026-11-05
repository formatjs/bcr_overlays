#include <cstdio>
#include <memory>
#include <string>
#include <string_view>
#include <vector>

#include "base/at_exit.h"
#include "base/command_line.h"
#include "base/containers/span.h"
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
#include "third_party/blink/renderer/core/css/parser/css_tokenizer.h"
#include "third_party/blink/renderer/core/html/parser/html_parser_options.h"
#include "third_party/blink/renderer/core/html/parser/html_tokenizer.h"
#include "third_party/blink/renderer/core/html_tokenizer_names.h"
#include "third_party/blink/renderer/platform/language.h"
#include "third_party/blink/renderer/platform/text/segmented_string.h"
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

std::vector<std::string> TokenizeHtml(const std::string& html,
                                      size_t chunk_size) {
  blink::HTMLParserOptions options;
  blink::HTMLTokenizer tokenizer(options);
  blink::SegmentedString input;
  std::vector<std::string> events;
  auto drain = [&] {
    while (auto* token = tokenizer.NextToken(input)) {
      switch (token->GetType()) {
        case blink::HTMLToken::DOCTYPE:
          events.push_back("doctype:" + token->GetName().AsString().Utf8());
          break;
        case blink::HTMLToken::kStartTag: {
          std::string event = "start:" + token->GetName().AsString().Utf8();
          for (const auto& attribute : token->Attributes()) {
            event += " " + attribute.GetName().GetString().Utf8() + "=" +
                     attribute.Value().Utf8();
          }
          if (token->SelfClosing()) {
            event += " /";
          }
          events.push_back(event);
          tokenizer.UpdateStateFor(*token);
          break;
        }
        case blink::HTMLToken::kEndTag:
          events.push_back("end:" + token->GetName().AsString().Utf8());
          break;
        case blink::HTMLToken::kComment:
          events.push_back("comment:" + token->Data().AsString().Utf8());
          break;
        case blink::HTMLToken::kCharacter:
          if (events.empty() || !events.back().starts_with("text:")) {
            events.emplace_back("text:");
          }
          events.back() += token->Data().AsString().Utf8();
          break;
        case blink::HTMLToken::kEndOfFile:
          events.emplace_back("eof");
          tokenizer.ClearToken();
          return;
        default:
          events.emplace_back("unexpected token");
          break;
      }
      tokenizer.ClearToken();
    }
  };
  for (size_t offset = 0; offset < html.size(); offset += chunk_size) {
    input.Append(blink::SegmentedString(blink::String::FromUTF8(
        std::string_view(html).substr(offset, chunk_size))));
    drain();
  }
  const UChar end = blink::kEndOfFileMarker;
  input.Append(blink::SegmentedString(blink::String(base::span_from_ref(end))));
  input.Close();
  drain();
  return events;
}
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
  blink::html_tokenizer_names::Init();
  CHECK_CASE(blink::html_tokenizer_names::kDoctype == "doctype");

  const std::string html =
      "<!doctype html><DIV data-x=\"A&amp;&#x1F469;\" title='x&ampy'>"
      "e&#x301;&NotEqualTilde;\r\n<!--ok--><br/>"
      "<script>if(a<b) x='&amp;';</script></DIV>";
  const std::vector<std::string> expected = {
      "doctype:html",
      "start:div data-x=A&\U0001F469 title=x&ampy",
      "text:e\u0301\u2242\u0338\n",
      "comment:ok",
      "start:br /",
      "start:script",
      "text:if(a<b) x='&amp;';",
      "end:script",
      "end:div",
      "eof"};
  for (size_t chunk_size = 1; chunk_size <= html.size(); ++chunk_size) {
    CHECK_CASE(TokenizeHtml(html, chunk_size) == expected);
  }
  const std::string malformed =
      "<p a='&#x0;' b='&ampy'>x&#x80;&#x110000;<!--unterminated";
  const std::vector<std::string> recovered = {"start:p a=\ufffd b=&ampy",
                                              "text:x\u20ac\ufffd",
                                              "comment:unterminated", "eof"};
  for (size_t chunk_size = 1; chunk_size <= malformed.size(); ++chunk_size) {
    CHECK_CASE(TokenizeHtml(malformed, chunk_size) == recovered);
  }

  const blink::String css(R"CSS(/*ignored*/ \63 olor:rebeccapurple;
      width:calc(100% - 1.25e2px); content:"\1f469 ";
      url(bad"quote); "bad
next)CSS");
  blink::CSSTokenizer tokenizer(css);
  auto next = [&] {
    auto token = tokenizer.TokenizeSingle();
    while (token.GetType() == blink::kWhitespaceToken) {
      token = tokenizer.TokenizeSingle();
    }
    return token;
  };
  auto token = next();
  CHECK_CASE(token.GetType() == blink::kIdentToken);
  CHECK_CASE(token.Value().ToString() == "color");
  CHECK_CASE(next().GetType() == blink::kColonToken);
  token = next();
  CHECK_CASE(token.GetType() == blink::kIdentToken);
  CHECK_CASE(token.Id() == blink::CSSValueID::kRebeccapurple);
  CHECK_CASE(next().GetType() == blink::kSemicolonToken);
  CHECK_CASE(next().Value().ToString() == "width");
  CHECK_CASE(next().GetType() == blink::kColonToken);
  token = next();
  CHECK_CASE(token.GetType() == blink::kFunctionToken);
  CHECK_CASE(token.FunctionId() == blink::CSSValueID::kCalc);
  token = next();
  CHECK_CASE(token.GetType() == blink::kPercentageToken);
  CHECK_CASE(token.NumericValue() == 100);
  CHECK_CASE(next().GetType() == blink::kDelimiterToken);
  token = next();
  CHECK_CASE(token.GetType() == blink::kDimensionToken);
  CHECK_CASE(token.NumericValue() == 125);
  CHECK_CASE(token.GetUnitType() ==
             blink::CSSPrimitiveValue::UnitType::kPixels);
  CHECK_CASE(next().GetType() == blink::kRightParenthesisToken);
  CHECK_CASE(next().GetType() == blink::kSemicolonToken);
  CHECK_CASE(next().Value().ToString() == "content");
  CHECK_CASE(next().GetType() == blink::kColonToken);
  token = next();
  CHECK_CASE(token.GetType() == blink::kStringToken);
  CHECK_CASE(token.Value().ToString().Utf8() == "\U0001F469");
  CHECK_CASE(next().GetType() == blink::kSemicolonToken);
  CHECK_CASE(next().GetType() == blink::kBadUrlToken);
  CHECK_CASE(next().GetType() == blink::kSemicolonToken);
  CHECK_CASE(next().GetType() == blink::kBadStringToken);
  CHECK_CASE(next().Value().ToString() == "next");
  CHECK_CASE(next().GetType() == blink::kEOFToken);
  return 0;
}
