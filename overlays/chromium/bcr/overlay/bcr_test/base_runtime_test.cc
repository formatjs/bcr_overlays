#include <cstdlib>
#include <string>
#include <utility>

#include "base/at_exit.h"
#include "base/command_line.h"
#include "base/files/file_util.h"
#include "base/files/scoped_temp_dir.h"
#include "base/functional/bind.h"
#include "base/json/json_reader.h"
#include "base/logging.h"
#include "base/run_loop.h"
#include "base/strings/string_number_conversions.h"
#include "base/task/single_thread_task_executor.h"
#include "base/task/thread_pool.h"
#include "base/task/thread_pool/thread_pool_instance.h"
#include "base/values.h"
#include "partition_alloc/partition_alloc.h"

extern "C" void chromium_base_test_emit_log();

namespace {
std::string log_message;
int log_severity = -1;

bool CaptureLog(int severity, const char*, int, size_t start,
                const std::string& message) {
  log_message = message.substr(start);
  log_severity = severity;
  return true;
}
}  // namespace

int main(int argc, char** argv) {
  partition_alloc::PartitionAllocGlobalInit([](size_t) { std::abort(); });
  base::AtExitManager at_exit;
  base::CommandLine::Init(argc, argv);
  logging::LoggingSettings settings;
  settings.logging_dest = logging::LOG_NONE;
  if (!logging::InitLogging(settings)) return 1;
  logging::SetLogMessageHandler(CaptureLog);
  chromium_base_test_emit_log();
  logging::SetLogMessageHandler(nullptr);
  if (log_severity != logging::LOGGING_WARNING ||
      log_message.find("native Rust logging 142") == std::string::npos) return 2;

  constexpr char input[] = R"({/* Chromium */"answer":142,"items":[true,null,],})";
  auto parsed = base::JSONReader::Read(input, base::JSON_ALLOW_COMMENTS |
                                              base::JSON_ALLOW_TRAILING_COMMAS);
  if (!parsed || parsed->GetDict().FindInt("answer") != 142) return 3;
  if (base::JSONReader::Read(input, base::JSON_PARSE_RFC)) return 4;
  if (base::JSONReader::Read("{} trailing", base::JSON_PARSE_RFC)) return 5;
  double number = 0;
  if (!base::StringToDouble("1.2345678901234567", &number) ||
      base::NumberToString(number) != "1.2345678901234567") return 9;
  if (base::StringToDouble("invalid", &number)) return 10;

  base::ScopedTempDir directory;
  if (!directory.CreateUniqueTempDir()) return 6;
  const std::string binary("native\0base", 11);
  const auto path = directory.GetPath().AppendASCII("roundtrip.bin");
  std::string read;
  if (!base::WriteFile(path, binary) || !base::ReadFileToString(path, &read) ||
      read != binary) return 7;

  base::SingleThreadTaskExecutor executor(base::MessagePumpType::UI);
  base::ThreadPoolInstance::CreateAndStartWithDefaultParams("NativeBase");
  base::RunLoop run_loop;
  int result = 0;
  base::ThreadPool::PostTaskAndReplyWithResult(
      FROM_HERE, base::BindOnce([] { return 142; }),
      base::BindOnce([](int* output, base::OnceClosure quit, int value) {
        *output = value;
        std::move(quit).Run();
      }, &result, run_loop.QuitClosure()));
  run_loop.Run();
  base::ThreadPoolInstance::Get()->Shutdown();
  return result == 142 ? 0 : 8;
}
