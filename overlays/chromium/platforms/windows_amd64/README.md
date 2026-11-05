# Windows AMD64

MSVC ABI with hermeticbuild LLVM and libc++. PartitionAlloc's 66 C++ sources
compile; `//tools/ci:allocator-windows-amd64` links a heap smoke executable.
CI hands that executable from Linux to a native Windows runner.

Static CRT selection uses `with_cfg` on the `features` build option because
LLVM selects its runtime libraries from the global configuration. Full browser
translation remains pending.
