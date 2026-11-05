#include <array>
#include <cstdio>
#include <cstring>
#include <string>

#include "third_party/abseil-cpp/absl/base/options.h"
#include "third_party/abseil-cpp/absl/container/flat_hash_map.h"
#include "third_party/abseil-cpp/absl/strings/str_format.h"
#include "third_party/boringssl/src/include/openssl/bio.h"
#include "third_party/boringssl/src/include/openssl/ec_key.h"
#include "third_party/boringssl/src/include/openssl/err.h"
#include "third_party/boringssl/src/include/openssl/evp.h"
#include "third_party/boringssl/src/include/openssl/md5.h"
#include "third_party/boringssl/src/include/openssl/rand.h"
#include "third_party/boringssl/src/include/openssl/sha.h"
#include "third_party/boringssl/src/include/openssl/ssl.h"
#include "third_party/boringssl/src/include/openssl/x509.h"
#include "third_party/boringssl/src/include/openssl/x509v3.h"

static_assert(ABSL_OPTION_HARDENED == 1);

std::string Hex(const uint8_t* data, size_t size) {
  std::string result;
  for (size_t index = 0; index < size; ++index) result += absl::StrFormat("%02x", data[index]);
  return result;
}

bool HashesWork() {
  const auto* input = reinterpret_cast<const uint8_t*>("abc");
  std::array<uint8_t, SHA256_DIGEST_LENGTH> sha256;
  std::array<uint8_t, SHA_DIGEST_LENGTH> sha1;
  std::array<uint8_t, MD5_DIGEST_LENGTH> md5;
  SHA256(input, 3, sha256.data());
  SHA1(input, 3, sha1.data());
  MD5(input, 3, md5.data());
  if (Hex(sha256.data(), sha256.size()) != "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad") return false;
  if (Hex(sha1.data(), sha1.size()) != "a9993e364706816aba3e25717850c26c9cd0d89d") return false;
  if (Hex(md5.data(), md5.size()) != "900150983cd24fb0d6963f7d28e17f72") return false;
  std::array<uint8_t, 32> entropy;
  return RAND_bytes(entropy.data(), entropy.size()) == 1;
}

bool TlsFailure(int line) {
  std::fprintf(stderr, "TLS fixture failed at line %d\n", line);
  return false;
}

bool HandshakeWorks() {
  bssl::UniquePtr<EC_KEY> ec(EC_KEY_new_by_curve_name(NID_X9_62_prime256v1));
  bssl::UniquePtr<EVP_PKEY> key(EVP_PKEY_new());
  bssl::UniquePtr<X509> cert(X509_new());
  if (!ec || !key || !cert || !EC_KEY_generate_key(ec.get()) ||
      !EVP_PKEY_set1_EC_KEY(key.get(), ec.get())) return TlsFailure(__LINE__);
  if (!X509_set_version(cert.get(), 2) || !ASN1_INTEGER_set(X509_get_serialNumber(cert.get()), 1) ||
      !X509_gmtime_adj(X509_getm_notBefore(cert.get()), -60) ||
      !X509_gmtime_adj(X509_getm_notAfter(cert.get()), 3600) ||
      !X509_set_pubkey(cert.get(), key.get())) return TlsFailure(__LINE__);
  auto* name = X509_get_subject_name(cert.get());
  const char hostname[] = "native.chromium.test";
  if (!X509_NAME_add_entry_by_txt(name, "CN", MBSTRING_ASC,
      reinterpret_cast<const unsigned char*>(hostname), -1, -1, 0) ||
      !X509_set_issuer_name(cert.get(), name)) return TlsFailure(__LINE__);
  bssl::UniquePtr<X509_EXTENSION> constraint(X509V3_EXT_nconf_nid(nullptr, nullptr,
      NID_basic_constraints, "critical,CA:TRUE"));
  if (!constraint || !X509_add_ext(cert.get(), constraint.get(), -1) ||
      !X509_sign(cert.get(), key.get(), EVP_sha256())) return TlsFailure(__LINE__);
  bssl::UniquePtr<SSL_CTX> client_context(SSL_CTX_new(TLS_method()));
  bssl::UniquePtr<SSL_CTX> server_context(SSL_CTX_new(TLS_method()));
  if (!client_context || !server_context ||
      !SSL_CTX_set_min_proto_version(client_context.get(), TLS1_3_VERSION) ||
      !SSL_CTX_set_min_proto_version(server_context.get(), TLS1_3_VERSION) ||
      !SSL_CTX_use_certificate(server_context.get(), cert.get()) ||
      !SSL_CTX_use_PrivateKey(server_context.get(), key.get()) ||
      !X509_STORE_add_cert(SSL_CTX_get_cert_store(client_context.get()), cert.get())) return TlsFailure(__LINE__);
  SSL_CTX_set_verify(client_context.get(), SSL_VERIFY_PEER, nullptr);
  bssl::UniquePtr<SSL> client(SSL_new(client_context.get()));
  bssl::UniquePtr<SSL> server(SSL_new(server_context.get()));
  if (!client || !server || !X509_VERIFY_PARAM_set1_host(
      SSL_get0_param(client.get()), hostname, sizeof(hostname) - 1)) return TlsFailure(__LINE__);
  BIO* client_bio = nullptr;
  BIO* server_bio = nullptr;
  if (!BIO_new_bio_pair(&client_bio, 0, &server_bio, 0)) return TlsFailure(__LINE__);
  SSL_set_bio(client.get(), client_bio, client_bio);
  SSL_set_bio(server.get(), server_bio, server_bio);
  SSL_set_connect_state(client.get());
  SSL_set_accept_state(server.get());
  for (int attempt = 0; attempt < 64; ++attempt) {
    for (auto* peer : {client.get(), server.get()}) {
      const int result = SSL_do_handshake(peer);
      if (result == 1) continue;
      const int error = SSL_get_error(peer, result);
      if (error != SSL_ERROR_WANT_READ && error != SSL_ERROR_WANT_WRITE) return TlsFailure(__LINE__);
    }
    if (SSL_is_init_finished(client.get()) && SSL_is_init_finished(server.get())) break;
  }
  if (!SSL_is_init_finished(client.get()) || !SSL_is_init_finished(server.get()) ||
      SSL_version(client.get()) != TLS1_3_VERSION || SSL_get_verify_result(client.get()) != X509_V_OK) return TlsFailure(__LINE__);
  const std::string message("native\0TLS", 10);
  std::array<char, 64> buffer;
  const int written = SSL_write(client.get(), message.data(), message.size());
  const int read = SSL_read(server.get(), buffer.data(), buffer.size());
  if (written != static_cast<int>(message.size()) || read != static_cast<int>(message.size()) ||
      std::memcmp(buffer.data(), message.data(), message.size()) != 0) {
    std::fprintf(stderr, "TLS transfer: write=%d read=%d error=%d\n", written, read, SSL_get_error(server.get(), read));
    return TlsFailure(__LINE__);
  }
  return true;
}

int main() {
  absl::flat_hash_map<int, std::string> values = {{142, "Chromium"}};
  if (values.at(142) != "Chromium" || !HashesWork()) return 1;
  if (!HandshakeWorks()) {
    ERR_print_errors_fp(stderr);
    return 2;
  }
  return 0;
}
