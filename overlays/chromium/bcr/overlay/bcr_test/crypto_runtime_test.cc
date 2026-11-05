#include <algorithm>
#include <array>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

#include "base/at_exit.h"
#include "base/base_paths.h"
#include "base/command_line.h"
#include "base/feature_list.h"
#include "base/files/file_path.h"
#include "base/files/file_util.h"
#include "base/path_service.h"
#include "base/strings/string_number_conversions.h"
#include "components/cbor/reader.h"
#include "components/cbor/writer.h"
#include "crypto/aead.h"
#include "crypto/cose.h"
#include "crypto/hash.h"
#include "crypto/hkdf.h"
#include "crypto/keypair.h"
#include "crypto/nss_key_util.h"
#include "crypto/nss_util.h"
#include "crypto/pem.h"
#include "crypto/sign.h"
#include "partition_alloc/partition_alloc.h"
#include "third_party/boringssl/src/pki/pem.h"

#include <cryptohi.h>
#include <keyhi.h>
#include <pk11pub.h>
#include <prerror.h>
#include <secitem.h>

#define CHECK_CASE(condition)                                              \
  do {                                                                     \
    if (!(condition)) {                                                    \
      std::fprintf(stderr, "line %d: %s (NSS %d)\n", __LINE__, #condition, \
                   PR_GetError());                                         \
      return 1;                                                            \
    }                                                                      \
  } while (false)

int main(int argc, char** argv) {
  partition_alloc::PartitionAllocGlobalInit([](size_t) { std::abort(); });
  base::AtExitManager at_exit;
  base::CommandLine::Init(argc, argv);
  base::FeatureList::InitInstance("", "");
  const char* temporary = std::getenv("TEST_TMPDIR");
  CHECK_CASE(temporary && base::PathService::Override(
                              base::DIR_HOME, base::FilePath(temporary)));
  crypto::EnsureNSSInit();

  const std::array<uint8_t, 32> expected_hash = {
      0xba, 0x78, 0x16, 0xbf, 0x8f, 0x01, 0xcf, 0xea, 0x41, 0x41, 0x40,
      0xde, 0x5d, 0xae, 0x22, 0x23, 0xb0, 0x03, 0x61, 0xa3, 0x96, 0x17,
      0x7a, 0x9c, 0xb4, 0x10, 0xff, 0x61, 0xf2, 0x00, 0x15, 0xad};
  CHECK_CASE(crypto::hash::Sha256("abc") == expected_hash);
  std::array<uint8_t, 32> nss_hash;
  CHECK_CASE(PK11_HashBuf(SEC_OID_SHA256, nss_hash.data(),
                          reinterpret_cast<const unsigned char*>("abc"),
                          3) == SECSuccess);
  CHECK_CASE(nss_hash == expected_hash);

  const base::FilePath pem_path =
      base::FilePath(temporary).AppendASCII("binary.pem");
  const std::string pem =
      "-----BEGIN BINARY DATA-----\nTgBTUw==\n-----END BINARY DATA-----\n";
  CHECK_CASE(base::WriteFile(pem_path, pem));
  const std::array<uint8_t, 4> pem_body = {'N', 0, 'S', 'S'};
  auto decoded_pem =
      crypto::pem::SingleMessageFromFile(pem_path, "BINARY DATA");
  CHECK_CASE(decoded_pem && std::ranges::equal(*decoded_pem, pem_body));
  const auto pem_messages =
      crypto::pem::MessagesFromFile(pem_path, {"BINARY DATA"});
  CHECK_CASE(pem_messages.size() == 1 &&
             pem_messages[0].type == "BINARY DATA" &&
             pem_messages[0].data == std::string("N\0SS", 4));
  CHECK_CASE(!crypto::pem::SingleMessageFromFile(pem_path, "CERTIFICATE"));
  CHECK_CASE(base::WriteFile(pem_path, pem + pem));
  CHECK_CASE(!crypto::pem::SingleMessageFromFile(pem_path, "BINARY DATA"));

  std::array<uint8_t, 22> secret;
  secret.fill(0x0b);
  const std::array<uint8_t, 13> salt = {0, 1, 2, 3,  4,  5, 6,
                                        7, 8, 9, 10, 11, 12};
  const std::array<uint8_t, 10> info = {0xf0, 0xf1, 0xf2, 0xf3, 0xf4,
                                        0xf5, 0xf6, 0xf7, 0xf8, 0xf9};
  std::vector<uint8_t> expected_hkdf;
  CHECK_CASE(
      base::HexStringToBytes("3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5"
                             "db02d56ecc4c5bf34007208d5b887185865",
                             &expected_hkdf));
  CHECK_CASE(std::ranges::equal(crypto::HkdfSha256<42>(secret, salt, info),
                                expected_hkdf));

  std::array<uint8_t, 32> key = {};
  std::array<uint8_t, 12> nonce = {};
  crypto::Aead aead(crypto::Aead::AES_256_GCM);
  aead.Init(key);
  auto tag = aead.Seal(base::span<const uint8_t>(), nonce, {});
  const std::array<uint8_t, 16> expected_tag = {
      0x53, 0x0f, 0x8a, 0xfb, 0xc7, 0x45, 0x36, 0xb9,
      0xa9, 0x63, 0xb4, 0xf1, 0xc4, 0xcb, 0x73, 0x8b};
  CHECK_CASE(std::ranges::equal(tag, expected_tag));
  const std::array<uint8_t, 6> message = {'n', 'a', 0, 't', 'i', 0xff};
  std::array<uint8_t, 3> aad = {'h', 0, 'd'};
  auto ciphertext = aead.Seal(message, nonce, aad);
  auto plaintext = aead.Open(ciphertext, nonce, aad);
  CHECK_CASE(plaintext && std::ranges::equal(*plaintext, message));
  aad[0] ^= 1;
  CHECK_CASE(!aead.Open(ciphertext, nonce, aad));
  aad[0] ^= 1;
  ciphertext[0] ^= 1;
  CHECK_CASE(!aead.Open(ciphertext, nonce, aad));
  CHECK_CASE(!aead.Open(base::span(ciphertext).first(8u), nonce, aad));

  auto private_key = crypto::keypair::PrivateKey::GenerateRsa2048();
  auto public_key = crypto::keypair::PublicKey::FromPrivateKey(private_key);
  auto pkcs8 = private_key.ToPrivateKeyInfo();
  const auto spki = public_key.ToSubjectPublicKeyInfo();
  CHECK_CASE(crypto::keypair::PrivateKey::FromPrivateKeyInfo(pkcs8));
  pkcs8.push_back(0);
  CHECK_CASE(!crypto::keypair::PrivateKey::FromPrivateKeyInfo(pkcs8));
  pkcs8.pop_back();
  crypto::ScopedPK11Slot slot(PK11_GetInternalSlot());
  CHECK_CASE(slot);
  auto nss_private =
      crypto::ImportNSSKeyFromPrivateKeyInfo(slot.get(), pkcs8, false);
  CHECK_CASE(nss_private);
  crypto::ScopedSECKEYPublicKey nss_public(
      SECKEY_ConvertToPublicKey(nss_private.get()));
  CHECK_CASE(nss_public);
  crypto::ScopedSECItem nss_spki(
      SECKEY_EncodeDERSubjectPublicKeyInfo(nss_public.get()));
  CHECK_CASE(nss_spki && std::ranges::equal(
                             spki, base::span(nss_spki->data, nss_spki->len)));
  auto id_from_spki = crypto::MakeNssIdFromSpki(spki);
  auto id_from_key = crypto::MakeNssIdFromPublicKey(nss_public.get());
  CHECK_CASE(id_from_spki && id_from_key &&
             SECITEM_ItemsAreEqual(id_from_spki.get(), id_from_key.get()));
  auto looked_up_key =
      crypto::FindNSSKeyFromPublicKeyInfoInSlot(spki, slot.get());
  CHECK_CASE(looked_up_key);
  crypto::ScopedSECItem nss_signature(SECITEM_AllocItem(nullptr, nullptr, 0));
  CHECK_CASE(nss_signature);
  CHECK_CASE(SEC_SignData(nss_signature.get(), message.data(), message.size(),
                          nss_private.get(),
                          SEC_OID_PKCS1_SHA256_WITH_RSA_ENCRYPTION) ==
             SECSuccess);
  CHECK_CASE(crypto::sign::Verify(
      crypto::sign::RSA_PKCS1_SHA256, public_key, message,
      base::span(nss_signature->data, nss_signature->len)));
  auto signature =
      crypto::sign::Sign(crypto::sign::RSA_PKCS1_SHA256, private_key, message);
  SECItem signature_item = {siBuffer, signature.data(),
                            static_cast<unsigned int>(signature.size())};
  CHECK_CASE(VFY_VerifyData(message.data(), message.size(), nss_public.get(),
                            &signature_item,
                            SEC_OID_PKCS1_SHA256_WITH_RSA_ENCRYPTION,
                            nullptr) == SECSuccess);
  signature[0] ^= 1;
  CHECK_CASE(!crypto::sign::Verify(crypto::sign::RSA_PKCS1_SHA256, public_key,
                                   message, signature));
  CHECK_CASE(VFY_VerifyData(message.data(), message.size(), nss_public.get(),
                            &signature_item,
                            SEC_OID_PKCS1_SHA256_WITH_RSA_ENCRYPTION,
                            nullptr) == SECFailure);

  auto ec_private = crypto::keypair::PrivateKey::GenerateEcP256();
  auto ec_public = crypto::keypair::PublicKey::FromPrivateKey(ec_private);
  const auto point = ec_public.ToUncompressedForm();
  const auto cose = crypto::PublicKeyToCoseKey(ec_public);
  auto decoded = cbor::Reader::Read(cose);
  CHECK_CASE(decoded && decoded->is_map());
  const auto& map = decoded->GetMap();
  CHECK_CASE(map.at(cbor::Value(int64_t{1})).GetInteger() == 2);
  CHECK_CASE(map.at(cbor::Value(int64_t{3})).GetInteger() == -7);
  CHECK_CASE(map.at(cbor::Value(int64_t{-1})).GetInteger() == 1);
  CHECK_CASE(
      std::ranges::equal(map.at(cbor::Value(int64_t{-2})).GetBytestring(),
                         base::span(point).subspan(1u, 32u)));
  CHECK_CASE(
      std::ranges::equal(map.at(cbor::Value(int64_t{-3})).GetBytestring(),
                         base::span(point).subspan(33u, 32u)));
  CHECK_CASE(cbor::Writer::Write(*decoded) == std::optional(cose));
  cbor::Reader::DecoderError error;
  const std::array<uint8_t, 5> duplicate = {0xa2, 0x01, 0x00, 0x01, 0x01};
  CHECK_CASE(!cbor::Reader::Read(duplicate, &error));
  CHECK_CASE(error == cbor::Reader::DecoderError::DUPLICATE_KEY);
  const std::array<uint8_t, 2> nonminimal = {0x18, 0x00};
  CHECK_CASE(!cbor::Reader::Read(nonminimal, &error));
  CHECK_CASE(error == cbor::Reader::DecoderError::NON_MINIMAL_CBOR_ENCODING);
  return 0;
}
