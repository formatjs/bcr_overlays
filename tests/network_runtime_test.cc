#include <arpa/inet.h>
#include <poll.h>
#include <sys/socket.h>
#include <unistd.h>

#include <atomic>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <memory>
#include <string>
#include <thread>
#include <vector>

#include <brotli/encode.h>
#include <openssl/ec.h>
#include <openssl/evp.h>
#include <openssl/ssl.h>
#include <openssl/x509.h>
#include <openssl/x509v3.h>
#include <zstd.h>

#include "base/at_exit.h"
#include "base/base_paths.h"
#include "base/command_line.h"
#include "base/containers/span.h"
#include "base/feature_list.h"
#include "base/files/file_path.h"
#include "base/functional/bind.h"
#include "base/metrics/histogram_base.h"
#include "base/metrics/histogram_samples.h"
#include "base/metrics/statistics_recorder.h"
#include "base/path_service.h"
#include "base/run_loop.h"
#include "base/task/single_thread_task_executor.h"
#include "base/task/thread_pool/thread_pool_instance.h"
#include "base/timer/timer.h"
#include "net/base/io_buffer.h"
#include "net/base/net_errors.h"
#include "net/base/network_change_notifier.h"
#include "net/cert/test_root_certs.h"
#include "net/cert/x509_certificate.h"
#include "net/filter/zstd_source_stream.h"
#include "net/proxy_resolution/proxy_config_service_fixed.h"
#include "net/proxy_resolution/proxy_config_with_annotation.h"
#include "net/traffic_annotation/network_traffic_annotation.h"
#include "net/url_request/url_request.h"
#include "net/url_request/url_request_context.h"
#include "net/url_request/url_request_context_builder.h"
#include "partition_alloc/partition_alloc.h"
#include "url/gurl.h"

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

class Response final : public net::URLRequest::Delegate {
 public:
  explicit Response(base::RunLoop* loop) : loop_(loop) {}
  void OnResponseStarted(net::URLRequest* request, int error) override {
    if (error != net::OK) {
      Finish(error);
      return;
    }
    Read(request);
  }
  void OnReadCompleted(net::URLRequest* request, int bytes) override {
    if (bytes <= 0) {
      Finish(bytes);
      return;
    }
    body.append(buffer_->data(), bytes);
    Read(request);
  }
  void OnSSLCertificateError(net::URLRequest* request,
                             int error,
                             const net::SSLInfo&,
                             bool) override {
    request->CancelWithError(error);
    Finish(error);
  }
  std::string body;
  int result = net::ERR_IO_PENDING;

 private:
  void Finish(int error) {
    result = error;
    loop_->Quit();
  }
  void Read(net::URLRequest* request) {
    for (;;) {
      const int bytes = request->Read(buffer_.get(), buffer_->size());
      if (bytes == net::ERR_IO_PENDING)
        return;
      if (bytes <= 0) {
        Finish(bytes);
        return;
      }
      body.append(buffer_->data(), bytes);
    }
  }
  base::RunLoop* loop_;
  scoped_refptr<net::IOBufferWithSize> buffer_ =
      base::MakeRefCounted<net::IOBufferWithSize>(4096);
};

bool Fetch(net::URLRequestContext* context,
           const std::string& wire_body,
           const std::string& extra_headers,
           int expected,
           const std::string& expected_body = {},
           SSL_CTX* tls = nullptr,
           bool expect_request = true) {
  const int listener = socket(AF_INET, SOCK_STREAM | SOCK_CLOEXEC, 0);
  if (listener < 0)
    return false;
  sockaddr_in address{};
  address.sin_family = AF_INET;
  address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
  if (bind(listener, reinterpret_cast<sockaddr*>(&address), sizeof(address)) ||
      listen(listener, 1)) {
    close(listener);
    return false;
  }
  socklen_t size = sizeof(address);
  if (getsockname(listener, reinterpret_cast<sockaddr*>(&address), &size)) {
    close(listener);
    return false;
  }
  std::atomic<bool> got_request = false;
  std::atomic<int> tls_version = 0;
  std::thread server([&] {
    pollfd ready{listener, POLLIN, 0};
    if (poll(&ready, 1, 15000) != 1)
      return;
    const int client = accept(listener, nullptr, nullptr);
    if (client < 0)
      return;
    timeval timeout{5, 0};
    setsockopt(client, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
    setsockopt(client, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
    bssl::UniquePtr<SSL> ssl;
    if (tls) {
      ssl.reset(SSL_new(tls));
      if (!ssl || !SSL_set_fd(ssl.get(), client) ||
          SSL_accept(ssl.get()) != 1) {
        close(client);
        return;
      }
      tls_version = SSL_version(ssl.get());
    }
    std::string request;
    char buffer[4096];
    while (request.find("\r\n\r\n") == std::string::npos) {
      const ssize_t received = ssl ? SSL_read(ssl.get(), buffer, sizeof(buffer))
                                   : recv(client, buffer, sizeof(buffer), 0);
      if (received <= 0)
        break;
      request.append(buffer, received);
    }
    got_request = request.starts_with("GET /payload HTTP/1.1\r\n");
    const std::string wire =
        "HTTP/1.1 200 OK\r\nConnection: close\r\nContent-Length: " +
        std::to_string(wire_body.size()) + "\r\n" + extra_headers + "\r\n" +
        wire_body;
    size_t offset = 0;
    while (offset < wire.size()) {
      const ssize_t sent =
          ssl ? SSL_write(ssl.get(), wire.data() + offset,
                          static_cast<int>(wire.size() - offset))
              : send(client, wire.data() + offset, wire.size() - offset,
                     MSG_NOSIGNAL);
      if (sent <= 0)
        break;
      offset += sent;
    }
    close(client);
  });
  base::RunLoop loop;
  Response response(&loop);
  constexpr auto annotation =
      net::DefineNetworkTrafficAnnotation("native_network_runtime", R"(
        semantics { sender: "Native network runtime test"
          description: "Requests a loopback fixture." trigger: "Bazel test"
          data: "Fixed test payload." destination: LOCAL }
        policy { cookies_allowed: NO setting: "Test only."
          policy_exception_justification: "Test fixture." })");
  auto request = context->CreateRequest(
      GURL(std::string(tls ? "https://127.0.0.1:" : "http://127.0.0.1:") +
           std::to_string(ntohs(address.sin_port)) + "/payload"),
      net::DEFAULT_PRIORITY, &response, annotation);
  base::OneShotTimer deadline;
  deadline.Start(FROM_HERE, base::Seconds(15), loop.QuitClosure());
  request->Start();
  loop.Run();
  request.reset();
  server.join();
  close(listener);
  if (response.result != expected || got_request != expect_request ||
      (tls && expected == net::OK && tls_version != TLS1_3_VERSION) ||
      (expected == net::OK && response.body != expected_body)) {
    std::fprintf(
        stderr, "network result %d expected %d; bytes %zu expected %zu\n",
        response.result, expected, response.body.size(), expected_body.size());
    return false;
  }
  return true;
}

std::unique_ptr<net::URLRequestContext> MakeContext() {
  net::URLRequestContextBuilder builder;
  builder.DisableHttpCache();
  builder.set_enable_brotli(true);
  builder.set_enable_zstd(true);
  builder.set_proxy_config_service(
      std::make_unique<net::ProxyConfigServiceFixed>(
          net::ProxyConfigWithAnnotation::CreateDirect()));
  return builder.Build();
}

int main(int argc, char** argv) {
  partition_alloc::PartitionAllocGlobalInit([](size_t) { std::abort(); });
  base::AtExitManager at_exit;
  base::CommandLine::Init(argc, argv);
  base::FeatureList::InitInstance("", "");
  CHECK_CASE(base::PathService::Override(
      base::DIR_HOME, base::FilePath(std::getenv("TEST_TMPDIR"))));
  std::signal(SIGPIPE, SIG_IGN);
  base::SingleThreadTaskExecutor executor(base::MessagePumpType::IO);
  base::ThreadPoolInstance::CreateAndStartWithDefaultParams("network-test");
  auto notifier = net::NetworkChangeNotifier::CreateIfNeeded();
  {
    auto context = MakeContext();
    CHECK_CASE(context);
    std::string body(65537, 'Q');
    body.front() = '\0';
    body.back() = '\xff';
    CHECK_CASE(Fetch(context.get(), body, "", net::OK, body));

    std::string compressed(ZSTD_compressBound(body.size()), '\0');
    const size_t compressed_size = ZSTD_compress(
        compressed.data(), compressed.size(), body.data(), body.size(), 3);
    CHECK_CASE(!ZSTD_isError(compressed_size));
    compressed.resize(compressed_size);
    CHECK_CASE(Fetch(context.get(), compressed, "Content-Encoding: zstd\r\n",
                     net::OK, body));
    auto* histogram =
        base::StatisticsRecorder::FindHistogram("Net.ZstdFilter.Status");
    CHECK_CASE(histogram);
    const int error_bucket =
        static_cast<int>(net::ZstdDecodingStatus::kDecodingError);
    const auto previous_errors =
        histogram->SnapshotSamples()->GetCount(error_bucket);
    const std::string complete_frame = compressed;
    compressed.pop_back();
    // Chromium records truncated EOF in metrics and returns the decoded bytes.
    CHECK_CASE(Fetch(context.get(), compressed, "Content-Encoding: zstd\r\n",
                     net::OK));
    CHECK_CASE(histogram->SnapshotSamples()->GetCount(error_bucket) ==
               previous_errors + 1);
    compressed = complete_frame;
    compressed[0] ^= 1;
    CHECK_CASE(Fetch(context.get(), compressed, "Content-Encoding: zstd\r\n",
                     net::ERR_CONTENT_DECODING_FAILED));

    size_t brotli_size = BrotliEncoderMaxCompressedSize(body.size());
    std::string brotli(brotli_size, '\0');
    CHECK_CASE(BrotliEncoderCompress(
        5, BROTLI_DEFAULT_WINDOW, BROTLI_MODE_GENERIC, body.size(),
        reinterpret_cast<const uint8_t*>(body.data()), &brotli_size,
        reinterpret_cast<uint8_t*>(brotli.data())));
    brotli.resize(brotli_size);
    CHECK_CASE(Fetch(context.get(), brotli, "Content-Encoding: br\r\n", net::OK,
                     body));
    CHECK_CASE(Fetch(context.get(), "x", "Content-Length: 2\r\n",
                     net::ERR_RESPONSE_HEADERS_MULTIPLE_CONTENT_LENGTH));

    bssl::UniquePtr<EC_KEY> ec(EC_KEY_new_by_curve_name(NID_X9_62_prime256v1));
    bssl::UniquePtr<EVP_PKEY> key(EVP_PKEY_new());
    bssl::UniquePtr<X509> cert(X509_new());
    CHECK_CASE(ec && key && cert && EC_KEY_generate_key(ec.get()));
    CHECK_CASE(EVP_PKEY_set1_EC_KEY(key.get(), ec.get()));
    CHECK_CASE(X509_set_version(cert.get(), 2));
    CHECK_CASE(ASN1_INTEGER_set(X509_get_serialNumber(cert.get()), 1));
    CHECK_CASE(X509_gmtime_adj(X509_getm_notBefore(cert.get()), -60));
    CHECK_CASE(X509_gmtime_adj(X509_getm_notAfter(cert.get()), 3600));
    CHECK_CASE(X509_set_pubkey(cert.get(), key.get()));
    auto* subject = X509_get_subject_name(cert.get());
    CHECK_CASE(X509_NAME_add_entry_by_txt(
        subject, "CN", MBSTRING_ASC,
        reinterpret_cast<const unsigned char*>("native.test"), -1, -1, 0));
    CHECK_CASE(X509_set_issuer_name(cert.get(), subject));
    for (const auto& [nid, value] : std::vector<std::pair<int, const char*>>{
             {NID_basic_constraints, "critical,CA:TRUE"},
             {NID_key_usage, "critical,digitalSignature,keyCertSign"},
             {NID_ext_key_usage, "serverAuth"},
             {NID_subject_alt_name, "IP:127.0.0.1"}}) {
      bssl::UniquePtr<X509_EXTENSION> extension(
          X509V3_EXT_nconf_nid(nullptr, nullptr, nid, value));
      CHECK_CASE(extension && X509_add_ext(cert.get(), extension.get(), -1));
    }
    CHECK_CASE(X509_sign(cert.get(), key.get(), EVP_sha256()));
    bssl::UniquePtr<SSL_CTX> server(SSL_CTX_new(TLS_method()));
    CHECK_CASE(server &&
               SSL_CTX_set_min_proto_version(server.get(), TLS1_3_VERSION));
    CHECK_CASE(SSL_CTX_use_certificate(server.get(), cert.get()));
    CHECK_CASE(SSL_CTX_use_PrivateKey(server.get(), key.get()));
    CHECK_CASE(Fetch(context.get(), body, "", net::ERR_CERT_AUTHORITY_INVALID,
                     {}, server.get(), false));
    const int der_size = i2d_X509(cert.get(), nullptr);
    CHECK_CASE(der_size > 0);
    std::vector<uint8_t> der(der_size);
    auto* der_output = der.data();
    CHECK_CASE(i2d_X509(cert.get(), &der_output) == der_size);
    auto certificate = net::X509Certificate::CreateFromBytes(base::span(der));
    CHECK_CASE(certificate);
    {
      net::ScopedTestRoot trusted(certificate);
      CHECK_CASE(!trusted.IsEmpty());
      auto trusted_context = MakeContext();
      CHECK_CASE(
          Fetch(trusted_context.get(), body, "", net::OK, body, server.get()));
    }
  }
  base::RunLoop().RunUntilIdle();
  base::ThreadPoolInstance::Get()->Shutdown();
  notifier.reset();
  return 0;
}
