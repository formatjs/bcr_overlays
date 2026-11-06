#include <string>
#include <thread>

#include "base/at_exit.h"
#include "base/files/file_util.h"
#include "base/files/scoped_temp_dir.h"
#include "base/json/json_reader.h"

int main() {
  base::AtExitManager at_exit;
  auto value = base::JSONReader::Read(R"({"name":"\u00e9","answer":42})");
  if (!value || !value->is_dict()) return 10;
  const auto* name = value->GetDict().FindString("name");
  if (!name || *name != "\xc3\xa9" ||
      value->GetDict().FindInt("answer") != 42) {
    return 11;
  }
  base::ScopedTempDir directory;
  if (!directory.CreateUniqueTempDir()) return 12;
  const auto path = directory.GetPath().Append(FILE_PATH_LITERAL("probe.json"));
  if (!base::WriteFile(path, "cross-compiled Chromium base")) return 13;
  std::string contents;
  if (!base::ReadFileToString(path, &contents) ||
      contents != "cross-compiled Chromium base") {
    return 14;
  }
  int result = 0;
  std::thread worker([&result] { result = 42; });
  worker.join();
  return result == 42 ? 0 : 15;
}
