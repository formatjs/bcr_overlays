#include <sqlite3.h>

const char* BcrSqliteVersion() {
  return sqlite3_libversion();
}
