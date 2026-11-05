# Chromium 142 compatibility modules

Thirteen independent module versions, staged together from Chromium's tested
dependency trees. Source archives keep their original integrity checks. Overlays
contain effective upstream and Chromium patches; patches are not replayed.

Each version records its base module and Chromium patch hashes in
`provenance.json`. Dependency versions match the combined workspace.

Use this registry before BCR:

```sh
cd compatibility_registry/tests
bazel build --registry="file://$(realpath ..)" \
  --registry=https://bcr.bazel.build //:libraries
bazel test --registry="file://$(realpath ..)" \
  --registry=https://bcr.bazel.build //:cpuinfo_consumer_test
```

All thirteen modules build in an independent consumer: fifteen native library
targets pass with hermetic LLVM. Its cpuinfo runtime test also passes. Codec
modules retain Chromium's tested NASM checker dependency floor.
Each module also passes a consumer with only that module and the compiler
dependencies. Run the same isolation check from the workspace root:

```sh
python3 tools/check_compatibility_modules.py
```

Each entry includes an independent `bcr_test` consumer and Linux presubmit job
for Bazel 9.2.0 with hermetic LLVM. The staged cpuinfo consumer builds and runs
its runtime test. Hosted BCR jobs have not run.
Standalone Chromium resolves from its actual registry archive and overlays;
native foundation and histogram generator probes pass. Full browser compilation
and runtime checks remain pending. Nothing published. Existing BCR maintainers
are preserved in each module's metadata.
The combined GitHub Actions job runs this consumer separately from Chromium.

Regenerate into a fresh directory with `tools/stage_compatibility_modules.py`;
existing module entries are immutable.
