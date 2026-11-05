#include <cstdio>
#include <cstdlib>
#include <memory>
#include <string>

#include "base/at_exit.h"
#include "base/files/file.h"
#include "base/files/memory_mapped_file.h"
#include "base/i18n/icu_util.h"
#include "partition_alloc/partition_alloc.h"
#include "rules_cc/cc/runfiles/runfiles.h"
#include "third_party/sqlite/sqlite3.h"

const char* BcrSqliteVersion();

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

int main(int argc, char** argv) {
  partition_alloc::PartitionAllocGlobalInit([](size_t) { std::abort(); });
  base::AtExitManager at_exit;
  CHECK_CASE(argc == 2);
  std::string error;
  std::unique_ptr<rules_cc::cc::runfiles::Runfiles> runfiles(
      rules_cc::cc::runfiles::Runfiles::CreateForTest(&error));
  CHECK_CASE(runfiles);
  base::File data(base::FilePath(runfiles->Rlocation(argv[1])),
                  base::File::FLAG_OPEN | base::File::FLAG_READ);
  CHECK_CASE(data.IsValid());
  CHECK_CASE(base::i18n::InitializeICUWithFileDescriptor(
      data.TakePlatformFile(), base::MemoryMappedFile::Region::kWholeFile));

  // Both implementations coexist: Chromium's renamed API and NSS's BCR SQLite.
  CHECK_CASE(std::string(sqlite3_libversion()) == "3.50.4");
  CHECK_CASE(std::string(BcrSqliteVersion()) == "3.51.1");
  CHECK_CASE(sqlite3_initialize() == SQLITE_OK);
  sqlite3* database = nullptr;
  CHECK_CASE(sqlite3_open(":memory:", &database) == SQLITE_OK);
  CHECK_CASE(sqlite3_exec(database, "CREATE TABLE payload(value BLOB UNIQUE)",
                          nullptr, nullptr, nullptr) == SQLITE_OK);
  sqlite3_stmt* statement = nullptr;
  CHECK_CASE(sqlite3_prepare_v2(database, "INSERT INTO payload VALUES(?)", -1,
                                &statement, nullptr) == SQLITE_OK);
  const std::string payload("\0\xff\x7f", 3);
  CHECK_CASE(sqlite3_bind_blob(statement, 1, payload.data(), payload.size(),
                               SQLITE_TRANSIENT) == SQLITE_OK);
  CHECK_CASE(sqlite3_step(statement) == SQLITE_DONE);
  CHECK_CASE(sqlite3_reset(statement) == SQLITE_OK);
  CHECK_CASE(sqlite3_step(statement) == SQLITE_CONSTRAINT);
  CHECK_CASE(sqlite3_finalize(statement) == SQLITE_CONSTRAINT);
  statement = nullptr;
  CHECK_CASE(sqlite3_exec(database,
                          "BEGIN;INSERT INTO payload VALUES(X'01');ROLLBACK;",
                          nullptr, nullptr, nullptr) == SQLITE_OK);
  CHECK_CASE(
      sqlite3_prepare_v2(database,
                         "SELECT value, lower('\xc3\x84\xc3\x96') FROM payload",
                         -1, &statement, nullptr) == SQLITE_OK);
  CHECK_CASE(sqlite3_step(statement) == SQLITE_ROW);
  CHECK_CASE(sqlite3_column_bytes(statement, 0) == 3);
  CHECK_CASE(
      std::string(static_cast<const char*>(sqlite3_column_blob(statement, 0)),
                  3) == payload);
  CHECK_CASE(std::string(reinterpret_cast<const char*>(
                 sqlite3_column_text(statement, 1))) == "\xc3\xa4\xc3\xb6");
  CHECK_CASE(sqlite3_step(statement) == SQLITE_DONE);
  CHECK_CASE(sqlite3_finalize(statement) == SQLITE_OK);
  statement = nullptr;

  // DQS=0 rejects a quoted string used as an identifier; API armor rejects null
  // DB.
  CHECK_CASE(sqlite3_prepare_v2(database, "SELECT \"not_a_column\"", -1,
                                &statement, nullptr) == SQLITE_ERROR);
  CHECK_CASE(sqlite3_prepare_v2(nullptr, "SELECT 1", -1, &statement, nullptr) ==
             SQLITE_MISUSE);
  CHECK_CASE(sqlite3_close(database) == SQLITE_OK);
  CHECK_CASE(sqlite3_shutdown() == SQLITE_OK);
  return 0;
}
