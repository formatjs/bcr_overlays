# Windows ARM64

MSVC ABI with hermeticbuild LLVM and libc++. PartitionAlloc's 66 C++ sources
compile; `//tools/ci:allocator-windows-arm64` links a heap smoke executable.
CI hands that executable from Linux to a native Windows ARM64 runner.

Static CRT selection shares the AMD64 `with_cfg` transition. Full browser
translation remains pending.
