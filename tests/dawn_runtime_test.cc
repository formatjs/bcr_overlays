#include <sys/resource.h>
#include <sys/wait.h>
#include <unistd.h>
#include <atomic>
#include <csignal>
#include <cstdio>
#include <thread>
#include <utility>

#include "dawn/common/Assert.h"
#include "dawn/dawn_proc.h"
#include "dawn/dawn_thread_dispatch_proc.h"
#include "dawn/webgpu_cpp.h"

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

namespace {
int first_handle;
int second_handle;
std::atomic<int> retained{0};
std::atomic<int> released{0};

WGPUInstance First(const WGPUInstanceDescriptor*) {
  return reinterpret_cast<WGPUInstance>(&first_handle);
}
WGPUInstance Second(const WGPUInstanceDescriptor*) {
  return reinterpret_cast<WGPUInstance>(&second_handle);
}
void Retain(WGPUInstance) {
  ++retained;
}
void Release(WGPUInstance) {
  ++released;
}
}  // namespace

int main() {
  // Opaque handles exercise generated dispatch and C++ ownership only.
  DawnProcTable first{};
  first.createInstance = First;
  first.instanceAddRef = Retain;
  first.instanceRelease = Release;
  DawnProcTable second = first;
  second.createInstance = Second;
  dawnProcSetProcs(&first);
  {
    wgpu::Instance instance = wgpu::CreateInstance();
    CHECK_CASE(instance.Get() == First(nullptr));
    auto copy = instance;
    auto moved = std::move(copy);
    CHECK_CASE(!copy && moved.Get() == instance.Get());
    CHECK_CASE(retained == 1 && released == 0);
  }
  CHECK_CASE(released == 2);

  dawnProcSetDefaultThreadProcs(&first);
  dawnProcSetProcs(&dawnThreadDispatchProcTable);
  dawnProcSetPerThreadProcs(&second);
  CHECK_CASE(wgpuCreateInstance(nullptr) == Second(nullptr));
  bool thread_ok = false;
  std::thread thread([&] {
    const bool inherited_default =
        wgpuCreateInstance(nullptr) == First(nullptr);
    dawnProcSetPerThreadProcs(&second);
    const bool local_override = wgpuCreateInstance(nullptr) == Second(nullptr);
    dawnProcSetPerThreadProcs(nullptr);
    thread_ok = inherited_default && local_override &&
                wgpuCreateInstance(nullptr) == First(nullptr);
  });
  thread.join();
  CHECK_CASE(thread_ok);
  CHECK_CASE(wgpuCreateInstance(nullptr) == Second(nullptr));
  dawnProcSetPerThreadProcs(nullptr);
  CHECK_CASE(wgpuCreateInstance(nullptr) == First(nullptr));
  dawnProcSetProcs(nullptr);
  dawnProcSetDefaultThreadProcs(nullptr);
  CHECK_CASE(wgpuCreateInstance(nullptr) == nullptr);

  const pid_t child = fork();
  CHECK_CASE(child >= 0);
  if (child == 0) {
    const rlimit limit{0, 0};
    setrlimit(RLIMIT_CORE, &limit);
    DAWN_ASSERT(false);
    _exit(0);
  }
  int status = 0;
  CHECK_CASE(waitpid(child, &status, 0) == child);
  CHECK_CASE(WIFSIGNALED(status) && WTERMSIG(status) == SIGABRT);
  return 0;
}
