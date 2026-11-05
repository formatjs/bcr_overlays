#include <algorithm>
#include <array>
#include <cstdio>
#include <vector>

#include "third_party/libsrtp/include/srtp.h"

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

int main() {
  CHECK_CASE(srtp_init() == srtp_err_status_ok);
  std::array<unsigned char, 30> key;
  for (size_t i = 0; i < key.size(); ++i)
    key[i] = static_cast<unsigned char>(i * 7 + 3);
  srtp_policy_t policy{};
  srtp_crypto_policy_set_aes_cm_128_hmac_sha1_80(&policy.rtp);
  srtp_crypto_policy_set_aes_cm_128_hmac_sha1_80(&policy.rtcp);
  policy.key = key.data();
  policy.window_size = 128;
  policy.ssrc.type = ssrc_any_outbound;
  srtp_t outbound = nullptr;
  CHECK_CASE(srtp_create(&outbound, &policy) == srtp_err_status_ok);
  policy.ssrc.type = ssrc_any_inbound;
  srtp_t inbound = nullptr;
  CHECK_CASE(srtp_create(&inbound, &policy) == srtp_err_status_ok);
  const std::vector<unsigned char> original = {
      0x80, 0x60, 0x00, 0x01, 0x00, 0x00, 0x10, 0x00, 0x12, 0x34, 0x56, 0x78,
      0x00, 0xff, 0x20, 0x80, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08};
  for (unsigned char sequence = 1; sequence <= 2; ++sequence) {
    auto clear = original;
    clear[3] = sequence;
    auto protected_packet = clear;
    protected_packet.resize(clear.size() + SRTP_MAX_TRAILER_LEN);
    int protected_size = static_cast<int>(clear.size());
    CHECK_CASE(srtp_protect(outbound, protected_packet.data(),
                            &protected_size) == srtp_err_status_ok);
    CHECK_CASE(protected_size == static_cast<int>(clear.size()) + 10);
    protected_packet.resize(protected_size);
    CHECK_CASE(!std::equal(clear.begin() + 12, clear.end(),
                           protected_packet.begin() + 12));
    auto tampered = protected_packet;
    tampered[15] ^= 1;
    int size = protected_size;
    CHECK_CASE(srtp_unprotect(inbound, tampered.data(), &size) ==
               srtp_err_status_auth_fail);
    auto received = protected_packet;
    size = protected_size;
    CHECK_CASE(srtp_unprotect(inbound, received.data(), &size) ==
               srtp_err_status_ok);
    received.resize(size);
    CHECK_CASE(received == clear);
    size = protected_size;
    CHECK_CASE(srtp_unprotect(inbound, protected_packet.data(), &size) ==
               srtp_err_status_replay_fail);
  }
  CHECK_CASE(srtp_dealloc(outbound) == srtp_err_status_ok);
  CHECK_CASE(srtp_dealloc(inbound) == srtp_err_status_ok);
  CHECK_CASE(srtp_shutdown() == srtp_err_status_ok);
  std::puts(
      "SRTP: native BoringSSL packet protection, authentication and replay "
      "rejection passed");
  return 0;
}
