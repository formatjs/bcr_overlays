#include <cerrno>
#include <fcntl.h>
#include <string>
#include <thread>
#include <unistd.h>

#include "linux_syscall_support.h"

int main() {
  const auto pid = sys_getpid();
  if (pid != getpid() || sys_gettid() != pid) return 1;
  pid_t worker_tid = 0;
  std::thread worker([&] { worker_tid = sys_gettid(); });
  worker.join();
  if (worker_tid <= 0 || worker_tid == pid) return 2;
  const int fd = sys_open("/proc/self/stat", O_RDONLY, 0);
  if (fd < 0) return 3;
  char buffer[1024];
  const auto count = sys_read(fd, buffer, sizeof(buffer));
  if (sys_close(fd) != 0 || count <= 0) return 4;
  const std::string record(buffer, count);
  if (!record.starts_with(std::to_string(pid) + " ")) return 5;
  errno = 0;
  if (sys_close(-1) != -1 || errno != EBADF) return 6;
  return 0;
}
