#include "base/debug/debugging_buildflags.h"

static_assert(BUILDFLAG(CAN_UNWIND_WITH_FRAME_POINTERS));
static_assert(BUILDFLAG(EXPENSIVE_DCHECKS_ARE_ON));
static_assert(BUILDFLAG(ENABLE_COMMANDLINE_SEQUENCE_CHECKS));
static_assert(!BUILDFLAG(DCHECK_IS_CONFIGURABLE));

int main() { return 0; }
