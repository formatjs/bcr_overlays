#include <cstdio>
#include <string>

#include "base/at_exit.h"
#include "fcp/confidentialcompute/crypto.h"

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

int main() {
  base::AtExitManager at_exit;
  namespace fcp_crypto = fcp::confidential_compute;
  auto signer = fcp_crypto::EcdsaP256R1Signer::Create();
  auto verifier =
      fcp_crypto::EcdsaP256R1SignatureVerifier::Create(signer.GetPublicKey());
  CHECK_CASE(verifier.ok());
  const std::string message("private\0metrics\xff", 16);
  std::string signature = signer.Sign(message);
  CHECK_CASE(verifier->Verify(message, signature).ok());
  CHECK_CASE(!verifier->Verify(message + "x", signature).ok());
  signature[0] ^= 1;
  CHECK_CASE(!verifier->Verify(message, signature).ok());
  CHECK_CASE(!fcp_crypto::EcdsaP256R1SignatureVerifier::Create("invalid").ok());

  fcp_crypto::MessageDecryptor recipient;
  auto public_key = recipient.GetPublicKey(
      [&](absl::string_view data) -> absl::StatusOr<std::string> {
        return signer.Sign(data);
      },
      -7);
  CHECK_CASE(public_key.ok());
  fcp_crypto::MessageEncryptor encryptor;
  const std::string associated_data("context\0v1", 10);
  auto encrypted = encryptor.Encrypt(message, *public_key, associated_data);
  CHECK_CASE(encrypted.ok());
  CHECK_CASE(encrypted->ciphertext != message);
  auto decrypted = recipient.Decrypt(encrypted->ciphertext, associated_data,
                                     encrypted->encrypted_symmetric_key,
                                     associated_data, encrypted->encapped_key);
  CHECK_CASE(decrypted.ok() && *decrypted == message);
  CHECK_CASE(!recipient
                  .Decrypt(encrypted->ciphertext, "wrong context",
                           encrypted->encrypted_symmetric_key, associated_data,
                           encrypted->encapped_key)
                  .ok());
  CHECK_CASE(!recipient
                  .Decrypt(encrypted->ciphertext, associated_data,
                           encrypted->encrypted_symmetric_key,
                           "wrong key context", encrypted->encapped_key)
                  .ok());
  fcp_crypto::MessageDecryptor stranger;
  CHECK_CASE(
      stranger
          .GetPublicKey(
              [&](absl::string_view data) -> absl::StatusOr<std::string> {
                return signer.Sign(data);
              },
              -7)
          .ok());
  CHECK_CASE(!stranger
                  .Decrypt(encrypted->ciphertext, associated_data,
                           encrypted->encrypted_symmetric_key, associated_data,
                           encrypted->encapped_key)
                  .ok());
  encrypted->ciphertext[0] ^= 1;
  CHECK_CASE(!recipient
                  .Decrypt(encrypted->ciphertext, associated_data,
                           encrypted->encrypted_symmetric_key, associated_data,
                           encrypted->encapped_key)
                  .ok());
  CHECK_CASE(
      !encryptor.Encrypt(message, "invalid public key", associated_data).ok());
  std::puts(
      "Confidential compute: native COSE/HPKE/AEAD, ECDSA, tamper/context/key "
      "rejection passed");
  return 0;
}
