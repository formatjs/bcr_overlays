#include <cstdio>
#include <type_traits>
#include <vector>

#include "api/location.h"
#include "api/task_queue/default_task_queue_factory.h"
#include "api/task_queue/task_queue_base.h"
#include "api/units/time_delta.h"
#include "base/at_exit.h"
#include "base/command_line.h"
#include "base/location.h"
#include "base/synchronization/waitable_event.h"
#include "base/task/thread_pool/thread_pool_instance.h"
#include "base/time/time.h"

static_assert(std::is_same_v<webrtc::Location, base::Location>);

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

int main(int argc, char** argv) {
  base::AtExitManager at_exit;
  base::CommandLine::Init(argc, argv);
  base::ThreadPoolInstance::CreateAndStartWithDefaultParams("WebRTC");
  auto factory = webrtc::CreateDefaultTaskQueueFactory();
  CHECK_CASE(factory);
  auto queue = factory->CreateTaskQueue(
      "Chromium queue", webrtc::TaskQueueFactory::Priority::NORMAL);
  CHECK_CASE(queue);
  base::WaitableEvent complete;
  std::vector<int> observed;
  bool correct_queue = true;
  for (int i = 0; i < 200; ++i) {
    queue->PostTask([&, i] {
      correct_queue &= webrtc::TaskQueueBase::Current() == queue.get();
      observed.push_back(i);
    });
  }
  queue->PostTask([&] { complete.Signal(); });
  CHECK_CASE(complete.TimedWait(base::Seconds(10)));
  CHECK_CASE(correct_queue && observed.size() == 200);
  for (int i = 0; i < 200; ++i)
    CHECK_CASE(observed[i] == i);
  base::WaitableEvent delayed;
  queue->PostDelayedTask([&] { delayed.Signal(); },
                         webrtc::TimeDelta::Millis(1));
  CHECK_CASE(delayed.TimedWait(base::Seconds(10)));
  queue.reset();
  factory.reset();
  base::ThreadPoolInstance::Get()->Shutdown();
  std::puts(
      "WebRTC: Chromium Location ABI, task order, current queue, delayed "
      "dispatch and teardown passed");
  return 0;
}
