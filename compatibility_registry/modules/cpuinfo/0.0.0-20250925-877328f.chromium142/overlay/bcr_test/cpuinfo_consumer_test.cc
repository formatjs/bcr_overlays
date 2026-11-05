#include <cpuinfo.h>
int main() {
  if (!cpuinfo_initialize()) return 1;
  const bool found_processors = cpuinfo_get_processors_count() > 0;
  cpuinfo_deinitialize();
  return found_processors ? 0 : 2;
}
