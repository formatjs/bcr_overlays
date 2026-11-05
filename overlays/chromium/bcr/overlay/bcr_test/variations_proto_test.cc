#include <csignal>
#include <string>
#include <sys/resource.h>
#include <sys/wait.h>
#include <unistd.h>

#include "components/variations/proto/variations_seed.pb.h"

static_assert(google::protobuf::internal::GetBoundsCheckMode() ==
              google::protobuf::internal::BoundsCheckMode::kAbort);

int main() {
  variations::VariationsSeed seed;
  seed.set_serial_number("native-seed");
  seed.set_version("142");
  const std::string expected = "\x0a\x0b" "native-seed" "\x22\x03" "142";
  if (seed.SerializeAsString() != expected) return 1;

  const std::string unknown = "\x98\x06\x07";
  variations::VariationsSeed parsed;
  if (!parsed.ParseFromString(expected + unknown)) return 1;
  if (parsed.serial_number() != "native-seed" || parsed.version() != "142") return 1;
  if (parsed.SerializeAsString() != expected + unknown) return 1;

  auto* study = seed.add_study();
  study->set_name("native-study");
  study->set_consistency(variations::Study::PERMANENT);
  auto* layer = seed.add_layers();
  layer->set_id(7);
  layer->set_num_slots(100);
  auto* member = layer->add_members();
  member->set_id(3);
  auto* slots = member->add_slots();
  slots->set_start(0);
  slots->set_end(49);
  if (!parsed.ParseFromString(seed.SerializeAsString())) return 1;
  if (parsed.study_size() != 1 || parsed.study(0).name() != "native-study" ||
      parsed.study(0).consistency() != variations::Study::PERMANENT ||
      parsed.layers_size() != 1 ||
      parsed.layers(0).members_size() != 1 ||
      parsed.layers(0).members(0).slots_size() != 1 ||
      parsed.layers(0).members(0).slots(0).end() != 49) return 1;

  variations::VariationsSeed missing_required;
  if (missing_required.ParseFromString(std::string("\x12\x00", 2))) return 1;

  variations::VariationsSeed unvalidated_utf8;
  const std::string bytes("\xff\xfe", 2);
  unvalidated_utf8.set_serial_number(bytes);
  if (!parsed.ParseFromString(unvalidated_utf8.SerializeAsString()) ||
      parsed.serial_number() != bytes) return 1;
  const pid_t child = fork();
  if (child < 0) return 1;
  if (child == 0) {
    const rlimit no_core = {0, 0};
    setrlimit(RLIMIT_CORE, &no_core);
    variations::VariationsSeed empty;
    (void)empty.study(0);
    _exit(0);
  }
  int status = 0;
  if (waitpid(child, &status, 0) != child || !WIFSIGNALED(status) ||
      WTERMSIG(status) != SIGABRT) return 1;
  return 0;
}
