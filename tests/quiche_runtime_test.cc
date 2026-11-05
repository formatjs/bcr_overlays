#include <cstdio>
#include <cstdlib>
#include <map>
#include <string>
#include <utility>

#include "absl/strings/escaping.h"
#include "base/at_exit.h"
#include "base/command_line.h"
#include "base/feature_list.h"
#include "openssl/hpke.h"
#include "partition_alloc/partition_alloc.h"
#include "quiche/binary_http/binary_http_message.h"
#include "quiche/common/platform/api/quiche_url_utils.h"
#include "quiche/http2/core/spdy_headers_handler_interface.h"
#include "quiche/http2/hpack/hpack_decoder_adapter.h"
#include "quiche/oblivious_http/oblivious_http_client.h"
#include "quiche/oblivious_http/oblivious_http_gateway.h"
#include "quiche/quic/core/proto/source_address_token.pb.h"

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

class Headers final : public spdy::SpdyHeadersHandlerInterface {
 public:
  void OnHeaderBlockStart() override {
    fields.clear();
    complete = false;
  }
  void OnHeader(absl::string_view key, absl::string_view value) override {
    fields.emplace(key, value);
  }
  void OnHeaderBlockEnd(size_t, size_t) override { complete = true; }
  std::map<std::string, std::string> fields;
  bool complete = false;
};

int main(int argc, char** argv) {
  partition_alloc::PartitionAllocGlobalInit([](size_t) { std::abort(); });
  base::AtExitManager at_exit;
  base::CommandLine::Init(argc, argv);
  base::FeatureList::InitInstance("", "");

  quic::SourceAddressToken token;
  token.set_ip(std::string("\x7f\0\0\1", 4));
  token.set_timestamp(123);
  CHECK_CASE(absl::BytesToHexString(token.SerializeAsString()) ==
             "0a047f000001107b");
  quic::SourceAddressToken parsed_token;
  CHECK_CASE(parsed_token.ParseFromString(token.SerializeAsString()));
  CHECK_CASE(parsed_token.ip() == token.ip() &&
             parsed_token.timestamp() == 123);
  CHECK_CASE(
      !parsed_token.ParseFromString(token.SerializeAsString().substr(0, 7)));

  // RFC 7541 C.4.1: Huffman-coded request, delivered one byte at a time.
  std::string wire;
  CHECK_CASE(
      absl::HexStringToBytes("828684418cf1e3c2e5f23a6ba0ab90f4ff", &wire));
  Headers headers;
  spdy::HpackDecoderAdapter decoder;
  decoder.HandleControlFrameHeadersStart(&headers);
  for (char byte : wire) {
    CHECK_CASE(decoder.HandleControlFrameHeadersData(&byte, 1));
  }
  CHECK_CASE(decoder.HandleControlFrameHeadersComplete());
  CHECK_CASE(headers.complete);
  const std::map<std::string, std::string> expected = {
      {":method", "GET"},
      {":scheme", "http"},
      {":path", "/"},
      {":authority", "www.example.com"}};
  CHECK_CASE(headers.fields == expected);
  // RFC 7541 C.4.2 reuses the previous block's dynamic table entry.
  CHECK_CASE(absl::HexStringToBytes("828684be5886a8eb10649cbf", &wire));
  decoder.HandleControlFrameHeadersStart(&headers);
  CHECK_CASE(decoder.HandleControlFrameHeadersData(wire.data(), wire.size()));
  CHECK_CASE(decoder.HandleControlFrameHeadersComplete());
  auto second_expected = expected;
  second_expected.emplace("cache-control", "no-cache");
  CHECK_CASE(headers.complete && headers.fields == second_expected);
  Headers invalid_headers;
  spdy::HpackDecoderAdapter invalid_decoder;
  invalid_decoder.HandleControlFrameHeadersStart(&invalid_headers);
  const char invalid_index = '\x80';
  CHECK_CASE(!invalid_decoder.HandleControlFrameHeadersData(&invalid_index, 1));
  CHECK_CASE(!invalid_headers.complete);

  // Chromium's URL override preserves RFC 6570 query expansion and ASCII rules.
  std::string expanded;
  CHECK_CASE(quiche::ExpandURITemplate("https://example.test/{path}{?query}",
                                       {{"path", "a/b"}, {"query", "x y"}},
                                       &expanded));
  CHECK_CASE(expanded == "https://example.test/a%2Fb?query=x%20y");
  CHECK_CASE(quiche::AsciiUrlDecode("a%2Fb") == "a/b");
  CHECK_CASE(!quiche::AsciiUrlDecode("%C3%A9").has_value());

  quiche::BinaryHttpRequest request(
      {"POST", "https", "example.test", "/upload"});
  request.AddHeaderField({"content-type", "application/octet-stream"});
  std::string body(65537, 'x');
  body[0] = '\0';
  body.back() = '\xff';
  request.set_body(body);
  auto serialized = request.Serialize();
  CHECK_CASE(serialized.ok());
  auto decoded = quiche::BinaryHttpRequest::Create(*serialized);
  CHECK_CASE(decoded.ok() && decoded->IsPayloadEqual(request));
  CHECK_CASE(
      !quiche::BinaryHttpRequest::Create(serialized->substr(0, 10)).ok());

  auto configuration = quiche::ObliviousHttpHeaderKeyConfig::Create(
      1, EVP_HPKE_DHKEM_X25519_HKDF_SHA256, EVP_HPKE_HKDF_SHA256,
      EVP_HPKE_AES_128_GCM);
  CHECK_CASE(configuration.ok());
  std::string private_key, public_key;
  CHECK_CASE(absl::HexStringToBytes(
      "b77431ecfa8f4cfc30d6e467aafa06944dffe28cb9dd1409e33a3045f5adc8a1",
      &private_key));
  CHECK_CASE(absl::HexStringToBytes(
      "6d21cfe09fbea5122f9ebc2eb2a69fcc4f06408cd54aac934f012e76fcdcef62",
      &public_key));
  auto client = quiche::ObliviousHttpClient::Create(public_key, *configuration);
  auto gateway =
      quiche::ObliviousHttpGateway::Create(private_key, *configuration);
  CHECK_CASE(client.ok() && gateway.ok());
  auto encrypted = client->CreateObliviousHttpRequest(*serialized);
  CHECK_CASE(encrypted.ok());
  std::string encrypted_wire = encrypted->EncapsulateAndSerialize();
  auto received = gateway->DecryptObliviousHttpRequest(encrypted_wire);
  CHECK_CASE(received.ok() && received->GetPlaintextData() == *serialized);
  encrypted_wire.back() ^= 1;
  CHECK_CASE(!gateway->DecryptObliviousHttpRequest(encrypted_wire).ok());
  CHECK_CASE(
      !gateway->DecryptObliviousHttpRequest(encrypted_wire.substr(0, 8)).ok());
  auto client_context = std::move(*encrypted).ReleaseContext();
  auto server_context = std::move(*received).ReleaseContext();
  auto response = gateway->CreateObliviousHttpResponse(body, server_context);
  CHECK_CASE(response.ok());
  std::string response_wire = response->EncapsulateAndSerialize();
  auto decrypted_response =
      client->DecryptObliviousHttpResponse(response_wire, client_context);
  CHECK_CASE(decrypted_response.ok() &&
             decrypted_response->GetPlaintextData() == body);
  response_wire.back() ^= 1;
  CHECK_CASE(
      !client->DecryptObliviousHttpResponse(response_wire, client_context)
           .ok());

  // RFC 9458 Appendix A decrypts independently of this library's encoder.
  CHECK_CASE(absl::HexStringToBytes(
      "3c168975674b2fa8e465970b79c8dcf09f1c741626480bd4c6162fc5b6a98e1a",
      &private_key));
  auto rfc_gateway =
      quiche::ObliviousHttpGateway::Create(private_key, *configuration);
  CHECK_CASE(rfc_gateway.ok());
  CHECK_CASE(absl::HexStringToBytes(
      "010020000100014b28f881333e7c164ffc499ad9796f877f4e1051ee6d31bad19dec96c2"
      "08b4726374e469135906992e1268c594d2a10c695d858c40a026e7965e7d86b83dd440b2"
      "c0185204b4d63525",
      &wire));
  auto rfc_request = rfc_gateway->DecryptObliviousHttpRequest(wire);
  CHECK_CASE(rfc_request.ok());
  CHECK_CASE(absl::BytesToHexString(rfc_request->GetPlaintextData()) ==
             "00034745540568747470730b6578616d706c652e636f6d012f");
  auto rfc_message =
      quiche::BinaryHttpRequest::Create(rfc_request->GetPlaintextData());
  CHECK_CASE(rfc_message.ok());
  CHECK_CASE(rfc_message->control_data().method == "GET");
  CHECK_CASE(rfc_message->control_data().authority == "example.com");
  CHECK_CASE(rfc_message->control_data().path == "/");
  return 0;
}
