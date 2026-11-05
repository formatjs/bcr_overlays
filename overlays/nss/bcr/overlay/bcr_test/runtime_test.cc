#include <sys/stat.h>
#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <string>

#include "cryptohi.h"
#include "keyhi.h"
#include "lib/freebl/loader.h"
#include "nss.h"
#include "pk11pub.h"
#include "prerror.h"
#include "prlink.h"
#include "prmem.h"
#include "secerr.h"
#include "secitem.h"
#include "secmod.h"

#define CHECK_CASE(condition)                                          \
  do {                                                                 \
    if (!(condition)) {                                                \
      std::fprintf(stderr, "line %d: %s (%d)\n", __LINE__, #condition, \
                   PR_GetError());                                     \
      return 1;                                                        \
    }                                                                  \
  } while (false)

int CheckSignature(SECKEYPrivateKey* key, SECKEYPublicKey* public_key) {
  unsigned char message[] = {'n', 'a', 't', 'i', 'v', 'e', 0, 'N', 'S', 'S'};
  SECItem signature = {siBuffer, nullptr, 0};
  CHECK_CASE(SEC_SignData(&signature, message, sizeof(message), key,
                          SEC_OID_PKCS1_SHA256_WITH_RSA_ENCRYPTION) ==
             SECSuccess);
  CHECK_CASE(VFY_VerifyData(message, sizeof(message), public_key, &signature,
                            SEC_OID_PKCS1_SHA256_WITH_RSA_ENCRYPTION,
                            nullptr) == SECSuccess);
  message[0] ^= 1;
  CHECK_CASE(VFY_VerifyData(message, sizeof(message), public_key, &signature,
                            SEC_OID_PKCS1_SHA256_WITH_RSA_ENCRYPTION,
                            nullptr) == SECFailure);
  SECITEM_FreeItem(&signature, PR_FALSE);
  return 0;
}

int CheckIntegrity(const std::string& temporary) {
  PRLibrary* library = PR_LoadLibrary("libfreeblpriv3.so");
  CHECK_CASE(library);
  PRFuncPtr entry = PR_FindFunctionSymbol(library, "FREEBL_GetVector");
  CHECK_CASE(entry);
  const FREEBLVector* vector = reinterpret_cast<FREEBLGetVectorFn*>(entry)();
  CHECK_CASE(vector && vector->p_BLAPI_SHVerifyFile);
  char* loaded_path = PR_GetLibraryFilePathname("libfreeblpriv3.so", entry);
  CHECK_CASE(loaded_path);
  std::filesystem::path original = std::filesystem::canonical(loaded_path);
  PR_Free(loaded_path);
  auto original_checksum = original;
  original_checksum.replace_extension(".chk");
  const auto copy = std::filesystem::path(temporary) / "module.so";
  auto checksum = copy;
  checksum.replace_extension(".chk");
  CHECK_CASE(std::filesystem::copy_file(original, copy));
  CHECK_CASE(std::filesystem::copy_file(original_checksum, checksum));
  std::filesystem::permissions(copy, std::filesystem::perms::owner_write,
                               std::filesystem::perm_options::add);
  std::filesystem::permissions(checksum, std::filesystem::perms::owner_write,
                               std::filesystem::perm_options::add);
  CHECK_CASE(vector->p_BLAPI_SHVerifyFile(copy.c_str()));
  {
    std::fstream bytes(copy, std::ios::binary | std::ios::in | std::ios::out);
    CHECK_CASE(bytes);
    const char first = bytes.get();
    bytes.seekp(0);
    bytes.put(first ^ 1);
    CHECK_CASE(bytes.good());
  }
  CHECK_CASE(!vector->p_BLAPI_SHVerifyFile(copy.c_str()));
  CHECK_CASE(std::filesystem::copy_file(
      original, copy, std::filesystem::copy_options::overwrite_existing));
  {
    std::fstream bytes(checksum,
                       std::ios::binary | std::ios::in | std::ios::out);
    CHECK_CASE(bytes);
    bytes.seekg(-1, std::ios::end);
    const char last = bytes.get();
    bytes.seekp(-1, std::ios::end);
    bytes.put(last ^ 1);
    CHECK_CASE(bytes.good());
  }
  CHECK_CASE(!vector->p_BLAPI_SHVerifyFile(copy.c_str()));
  CHECK_CASE(PR_UnloadLibrary(library) == PR_SUCCESS);
  return 0;
}

int CheckDatabase(const std::string& type, const std::string& directory) {
  CHECK_CASE(mkdir(directory.c_str(), 0700) == 0);
  const std::string location = type + ":" + directory;
  CHECK_CASE(NSS_InitReadWrite(location.c_str()) == SECSuccess);
  PK11SlotInfo* slot = PK11_GetInternalKeySlot();
  CHECK_CASE(slot);
  if (PK11_NeedUserInit(slot)) {
    CHECK_CASE(PK11_InitPin(slot, nullptr, "") == SECSuccess);
  }
  PK11RSAGenParams parameters = {2048, 65537};
  SECKEYPublicKey* public_key = nullptr;
  SECKEYPrivateKey* key =
      PK11_GenerateKeyPair(slot, CKM_RSA_PKCS_KEY_PAIR_GEN, &parameters,
                           &public_key, PR_TRUE, PR_TRUE, nullptr);
  CHECK_CASE(key && public_key);
  CHECK_CASE(PK11_SetPrivateKeyNickname(key, "native-bazel-key") == SECSuccess);
  CHECK_CASE(CheckSignature(key, public_key) == 0);
  SECKEY_DestroyPublicKey(public_key);
  SECKEY_DestroyPrivateKey(key);
  PK11_FreeSlot(slot);
  CHECK_CASE(NSS_Shutdown() == SECSuccess);

  CHECK_CASE(NSS_InitReadWrite(location.c_str()) == SECSuccess);
  slot = PK11_GetInternalKeySlot();
  CHECK_CASE(slot);
  SECKEYPrivateKeyList* keys =
      PK11_ListPrivKeysInSlot(slot, "native-bazel-key", nullptr);
  CHECK_CASE(keys && !PR_CLIST_IS_EMPTY(&keys->list));
  auto* node =
      reinterpret_cast<SECKEYPrivateKeyListNode*>(PR_LIST_HEAD(&keys->list));
  public_key = SECKEY_ConvertToPublicKey(node->key);
  CHECK_CASE(public_key && CheckSignature(node->key, public_key) == 0);
  SECKEY_DestroyPublicKey(public_key);
  SECKEY_DestroyPrivateKeyList(keys);
  PK11_FreeSlot(slot);
  CHECK_CASE(NSS_Shutdown() == SECSuccess);
  return 0;
}

int main(int argc, char** argv) {
  const bool fips = argc == 2 && std::strcmp(argv[1], "fips") == 0;
  if (fips) {
    const char* temporary = std::getenv("TEST_TMPDIR");
    CHECK_CASE(temporary);
    const std::string directory = std::string(temporary) + "/fips";
    CHECK_CASE(mkdir(directory.c_str(), 0700) == 0);
    CHECK_CASE(NSS_InitReadWrite(("sql:" + directory).c_str()) == SECSuccess);
    const std::string module_name = SECMOD_GetInternalModule()->commonName;
    CHECK_CASE(SECMOD_DeleteInternalModule(module_name.c_str()) == SECSuccess);
    CHECK_CASE(PK11_IsFIPS());
    PK11SlotInfo* slot = PK11_GetInternalKeySlot();
    CHECK_CASE(slot);
    if (PK11_NeedUserInit(slot)) {
      CHECK_CASE(PK11_InitPin(slot, nullptr, "weak") == SECFailure);
      CHECK_CASE(PR_GetError() == SEC_ERROR_INVALID_PASSWORD);
      CHECK_CASE(PK11_InitPin(slot, nullptr, "bazel-FIPS-password-7!") ==
                 SECSuccess);
    }
    CHECK_CASE(PK11_CheckUserPassword(slot, "bazel-FIPS-password-7!") ==
               SECSuccess);
    PK11_FreeSlot(slot);
  } else {
    CHECK_CASE(NSS_NoDB_Init(nullptr) == SECSuccess);
  }
  std::array<unsigned char, 32> hash;
  const std::array<unsigned char, 32> expected_hash = {
      0xba, 0x78, 0x16, 0xbf, 0x8f, 0x01, 0xcf, 0xea, 0x41, 0x41, 0x40,
      0xde, 0x5d, 0xae, 0x22, 0x23, 0xb0, 0x03, 0x61, 0xa3, 0x96, 0x17,
      0x7a, 0x9c, 0xb4, 0x10, 0xff, 0x61, 0xf2, 0x00, 0x15, 0xad};
  CHECK_CASE(PK11_HashBuf(SEC_OID_SHA256, hash.data(),
                          reinterpret_cast<const unsigned char*>("abc"),
                          3) == SECSuccess);
  CHECK_CASE(hash == expected_hash);
  PK11SlotInfo* slot = PK11_GetInternalSlot();
  CHECK_CASE(slot && PK11_DoesMechanism(slot, CKM_AES_GCM));
  std::array<unsigned char, 16> raw_key = {};
  SECItem key_data = {siBuffer, raw_key.data(), raw_key.size()};
  PK11SymKey* key = PK11_ImportSymKey(slot, CKM_AES_GCM, PK11_OriginUnwrap,
                                      CKA_ENCRYPT, &key_data, nullptr);
  if (fips) {
    CHECK_CASE(!key && PR_GetError() == SEC_ERROR_BAD_DATA);
    key = PK11_KeyGen(slot, CKM_AES_KEY_GEN, nullptr, 16, nullptr);
  }
  CHECK_CASE(key);
  std::array<unsigned char, 12> iv = {};
  CK_NSS_GCM_PARAMS parameters = {iv.data(), iv.size(), nullptr, 0, 128};
  SECItem parameter_data = {siBuffer,
                            reinterpret_cast<unsigned char*>(&parameters),
                            sizeof(parameters)};
  std::array<unsigned char, 32> ciphertext;
  unsigned char empty = 0;
  unsigned int size = 0;
  CHECK_CASE(PK11_Encrypt(key, CKM_AES_GCM, &parameter_data, ciphertext.data(),
                          &size, ciphertext.size(), &empty, 0) == SECSuccess);
  const std::array<unsigned char, 16> expected_tag = {
      0x58, 0xe2, 0xfc, 0xce, 0xfa, 0x7e, 0x30, 0x61,
      0x36, 0x7f, 0x1d, 0x57, 0xa4, 0xe7, 0x45, 0x5a};
  CHECK_CASE(size == expected_tag.size());
  if (!fips) {
    CHECK_CASE(std::memcmp(ciphertext.data(), expected_tag.data(), size) == 0);
  }
  unsigned int decoded_size = 1;
  CHECK_CASE(PK11_Decrypt(key, CKM_AES_GCM, &parameter_data, &empty,
                          &decoded_size, 1, ciphertext.data(),
                          size) == SECSuccess);
  CHECK_CASE(decoded_size == 0);
  ciphertext[0] ^= 1;
  CHECK_CASE(PK11_Decrypt(key, CKM_AES_GCM, &parameter_data, &empty,
                          &decoded_size, 1, ciphertext.data(),
                          size) == SECFailure);
  PK11_FreeSymKey(key);
  PK11_FreeSlot(slot);
  const char* temporary = std::getenv("TEST_TMPDIR");
  CHECK_CASE(temporary);
  CHECK_CASE(CheckIntegrity(temporary) == 0);
  CHECK_CASE(NSS_Shutdown() == SECSuccess);
  if (fips)
    return 0;
  CHECK_CASE(CheckDatabase("sql", std::string(temporary) + "/sql") == 0);
  CHECK_CASE(CheckDatabase("dbm", std::string(temporary) + "/dbm") == 0);
  return 0;
}
