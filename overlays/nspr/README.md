# NSPR native Bazel overlay

NSPR 4.29 matches Chromium 142's pinned Bullseye sysroot. Proposed module:
`nspr@4.29`. BCR has no `nspr` module metadata entry as of 2026-11-03.

Public targets:

- `@nspr//:nspr4`: complete Linux pthread runtime and x86_64 atomic assembly.
- `@nspr//:plc4`: portable strings, Base64, errors and command-line helpers.
- `@nspr//:plds4`: arenas and hash tables.
- `@nspr//:nspr`: all three static libraries.
- `@nspr//:shared`: shared libraries using one common NSPR runtime for NSS.

73 C sources and one assembly source compile through native Bazel actions.
Source lists import upstream Makefiles; consumers run no configure or Make.
No upstream source changes. Official Mozilla archive pinned by SHA-256.
The matching Debian `2:4.29-1` source package has no downstream patches.
Linux x86_64 only initially. Static and shared libraries supported.

Linux configuration follows upstream `configure.in` and `config/config.mk`:
pthread backend, logging, optimized release compilation and GNU interfaces.
The existing `gettid` syscall fallback supports hermetic LLVM's glibc 2.28
headers. `prcpucfg.h` uses upstream `_linux.cfg` unchanged. Version headers
retain library names while omitting wall-clock build timestamps.

Tests register hermeticbuild LLVM `llvm@0.8.26`. Published module leaves compiler
selection to consumers. Native NSS and Chromium crypto use the shared runtime.

## Validate

From repository root:

```sh
registry=$(mktemp -d)
python3 tools/stage_bcr_entry.py --source-registry overlays/nspr/bcr \
  --target-registry "$registry" --module nspr --version 4.29
cd overlays/nspr/tests
bazel test --registry="file://$registry" --registry=https://bcr.bazel.build \
  //:runtime_test //:shared_runtime_test
```

Runtime test loads an actual shared library through NSPR, exchanges 65 KB of
binary data over threaded TCP sockets, checks timeout and EOF, maps writable
file data, accesses a sparse file above 4 GiB and verifies missing-file errors.
PLC/PLDS checks cover binary Base64, arena allocation and hash insertion/removal.

Regenerate source lists from extracted pinned source:

```sh
python3 overlays/nspr/tools/import_sources.py /path/to/nspr-4.29/nspr
buildifier overlays/nspr/bcr/overlay/bazel/sources.bzl
```

Upstream license: MPL-2.0. No BCR publication yet; maintainers remain unset.
