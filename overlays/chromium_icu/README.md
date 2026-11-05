# Chromium ICU native Bazel overlay

Chromium 142's ICU 74.2 fork, pinned to
`1b2e3e8a421efae36141a7b932b41e315b089af8`.
Proposed module version: `74.2.chromium142`.

Separate `chromium_icu` module preserves Chromium locale data, word-break patches,
tracing and HTML conversion configuration. Existing BCR `icu` starts at 76.1;
reusing its name would allow dependency resolution to replace Chromium's fork.

Libraries link statically, matching `U_STATIC_IMPLEMENTATION` and hidden data
symbols. V8 Intl consumer validates this through default Bazel test linkage.

Public targets:

- `@chromium_icu//:icu`: common and internationalization libraries, embedded data.
- `@chromium_icu//:icu_file`: same implementation, external data initialization.
- `@chromium_icu//:common/icudtl.dat`: pinned Chromium locale data.

Native C++ compilation and declared upstream Python assembly generation only.
No GN, Ninja, CMake or foreign-build backend. Linux x86_64 supported initially.
Consumer tests register hermeticbuild LLVM `llvm@0.8.26`; published library leaves
compiler selection to consumers.

## Validate

From repository root:

```sh
registry=$(mktemp -d)
python3 tools/stage_bcr_entry.py --source-registry overlays/chromium_icu/bcr \
  --target-registry "$registry" --module chromium_icu --version 74.2.chromium142
cd overlays/chromium_icu/tests/bcr
bazel test --registry="file://$registry" --registry=https://bcr.bazel.build \
  //:static_data_test //:file_data_test
```

Both tests check actual ICU version, NFC normalization, French number formatting
and Chromium's patched word boundaries in `example.com`. File-data test retains
aligned data through ICU cleanup. Source lists import literal arrays from pinned
upstream `sources.gni`:

```sh
python3 overlays/chromium_icu/tools/import_sources.py /path/to/pinned/icu
```

Source archive comes from Chromium ICU maintainer Philip Jägenstedt's mirror.
Exact Git commit and tree match upstream; all 7,024 archive files were compared
with GoogleSource. GitHub archive has fixed SHA-256 in `bcr/source.json`.
GoogleSource dynamically generates tar metadata, changing archive checksums across
requests; published source must retain reproducible archive bytes.

No module published to BCR yet. Maintainers recorded in [bcr/metadata.json](bcr/metadata.json).
