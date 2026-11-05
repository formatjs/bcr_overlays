#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <string>
#include <vector>

#include "plarena.h"
#include "plbase64.h"
#include "plhash.h"
#include "pratom.h"
#include "prerror.h"
#include "prinit.h"
#include "prio.h"
#include "prlink.h"
#include "prmem.h"
#include "prthread.h"
#include "rules_cc/cc/runfiles/runfiles.h"

#define CHECK_CASE(condition)                                          \
  do {                                                                 \
    if (!(condition)) {                                                \
      std::fprintf(stderr, "line %d: %s (%d)\n", __LINE__, #condition, \
                   PR_GetError());                                     \
      return 1;                                                        \
    }                                                                  \
  } while (false)

struct Transfer {
  PRFileDesc* socket;
  PRInt32 count = 0;
  bool success = false;
};

void PR_CALLBACK Echo(void* argument) {
  auto* transfer = static_cast<Transfer*>(argument);
  std::vector<char> bytes(65537);
  size_t offset = 0;
  while (offset < bytes.size()) {
    const auto read =
        PR_Recv(transfer->socket, bytes.data() + offset, bytes.size() - offset,
                0, PR_SecondsToInterval(5));
    if (read <= 0)
      return;
    offset += read;
    PR_AtomicAdd(&transfer->count, read);
  }
  offset = 0;
  while (offset < bytes.size()) {
    const auto written =
        PR_Send(transfer->socket, bytes.data() + offset, bytes.size() - offset,
                0, PR_SecondsToInterval(5));
    if (written <= 0)
      return;
    offset += written;
  }
  transfer->success = PR_Close(transfer->socket) == PR_SUCCESS;
}

int main(int argc, char** argv) {
  PR_Init(PR_USER_THREAD, PR_PRIORITY_NORMAL, 0);
  CHECK_CASE(argc == 2);
  std::string error;
  std::unique_ptr<rules_cc::cc::runfiles::Runfiles> runfiles(
      rules_cc::cc::runfiles::Runfiles::CreateForTest(&error));
  CHECK_CASE(runfiles);
  const std::string module_path = runfiles->Rlocation(argv[1]);
  PRLibrary* module = PR_LoadLibrary(module_path.c_str());
  CHECK_CASE(module);
  auto function = reinterpret_cast<int (*)(int)>(
      PR_FindFunctionSymbol(module, "nspr_test_plugin"));
  CHECK_CASE(function && function(7) == 22);
  CHECK_CASE(PR_UnloadLibrary(module) == PR_SUCCESS);
  PRFileDesc* sockets[2];
  CHECK_CASE(PR_NewTCPSocketPair(sockets) == PR_SUCCESS);
  char pending;
  CHECK_CASE(
      PR_Recv(sockets[0], &pending, 1, 0, PR_MillisecondsToInterval(10)) == -1);
  CHECK_CASE(PR_GetError() == PR_IO_TIMEOUT_ERROR);
  Transfer transfer{sockets[1]};
  PRThread* worker =
      PR_CreateThread(PR_USER_THREAD, Echo, &transfer, PR_PRIORITY_NORMAL,
                      PR_GLOBAL_THREAD, PR_JOINABLE_THREAD, 0);
  CHECK_CASE(worker);
  std::vector<char> payload(65537);
  for (size_t i = 0; i < payload.size(); ++i)
    payload[i] = i % 251;
  size_t offset = 0;
  while (offset < payload.size()) {
    const auto written =
        PR_Send(sockets[0], payload.data() + offset, payload.size() - offset, 0,
                PR_SecondsToInterval(5));
    CHECK_CASE(written > 0);
    offset += written;
  }
  std::vector<char> received(payload.size());
  offset = 0;
  while (offset < received.size()) {
    const auto read =
        PR_Recv(sockets[0], received.data() + offset, received.size() - offset,
                0, PR_SecondsToInterval(5));
    CHECK_CASE(read > 0);
    offset += read;
  }
  CHECK_CASE(PR_JoinThread(worker) == PR_SUCCESS);
  CHECK_CASE(transfer.success && transfer.count == payload.size());
  CHECK_CASE(received == payload);
  CHECK_CASE(PR_Recv(sockets[0], &pending, 1, 0, PR_SecondsToInterval(5)) == 0);
  CHECK_CASE(PR_Close(sockets[0]) == PR_SUCCESS);

  const char* temporary = std::getenv("TEST_TMPDIR");
  CHECK_CASE(temporary);
  const std::string path = std::string(temporary) + "/nspr-runtime";
  PRFileDesc* file =
      PR_Open(path.c_str(), PR_RDWR | PR_CREATE_FILE | PR_TRUNCATE, 0600);
  CHECK_CASE(file);
  CHECK_CASE(PR_Write(file, payload.data(), payload.size()) == payload.size());
  PRFileMap* mapping =
      PR_CreateFileMap(file, payload.size(), PR_PROT_READWRITE);
  CHECK_CASE(mapping);
  void* memory = PR_MemMap(mapping, 0, 4096);
  CHECK_CASE(memory && std::memcmp(memory, payload.data(), 4096) == 0);
  static_cast<char*>(memory)[0] = 'X';
  CHECK_CASE(PR_MemUnmap(memory, 4096) == PR_SUCCESS);
  CHECK_CASE(PR_CloseFileMap(mapping) == PR_SUCCESS);
  CHECK_CASE(PR_Seek64(file, 0, PR_SEEK_SET) == 0);
  CHECK_CASE(PR_Read(file, &pending, 1) == 1 && pending == 'X');
  const PRInt64 large_offset = (PRInt64{1} << 32) + 7;
  CHECK_CASE(PR_Seek64(file, large_offset, PR_SEEK_SET) == large_offset);
  CHECK_CASE(PR_Write(file, "Z", 1) == 1);
  PRFileInfo64 info;
  CHECK_CASE(PR_GetOpenFileInfo64(file, &info) == PR_SUCCESS);
  CHECK_CASE(info.size == large_offset + 1);
  CHECK_CASE(PR_Close(file) == PR_SUCCESS);
  CHECK_CASE(PR_Delete(path.c_str()) == PR_SUCCESS);
  CHECK_CASE(!PR_Open(path.c_str(), PR_RDONLY, 0));
  CHECK_CASE(PR_GetError() == PR_FILE_NOT_FOUND_ERROR);

  const std::array<char, 4> binary = {'A', '\0', 'B', '\xff'};
  char* encoded = PL_Base64Encode(binary.data(), binary.size(), nullptr);
  CHECK_CASE(encoded && std::strcmp(encoded, "QQBC/w==") == 0);
  char* decoded = PL_Base64Decode(encoded, std::strlen(encoded), nullptr);
  CHECK_CASE(decoded &&
             std::memcmp(decoded, binary.data(), binary.size()) == 0);
  PR_Free(decoded);
  PR_Free(encoded);
  PLArenaPool pool;
  PL_InitArenaPool(&pool, "runtime", 4096, 8);
  void* value;
  PL_ARENA_ALLOCATE(value, &pool, 128);
  CHECK_CASE(value);
  PLHashTable* table = PL_NewHashTable(16, PL_HashString, PL_CompareStrings,
                                       PL_CompareValues, nullptr, nullptr);
  CHECK_CASE(table && PL_HashTableAdd(table, "key", value));
  CHECK_CASE(PL_HashTableLookup(table, "key") == value);
  CHECK_CASE(PL_HashTableRemove(table, "key"));
  CHECK_CASE(!PL_HashTableLookup(table, "key"));
  PL_HashTableDestroy(table);
  PL_FinishArenaPool(&pool);
  CHECK_CASE(PR_Cleanup() == PR_SUCCESS);
  return 0;
}
