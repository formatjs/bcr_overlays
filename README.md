# FormatJS BCR overlays

Native Bazel overlays, maintained in one repository and published as separate
Bazel Central Registry modules. No umbrella `bcr_overlays` module.

- [Chromium](overlays/chromium): native foundation builds and tests; full browser pending.
- Planned: [V8](overlays/v8), [Skia](overlays/skia), [ANGLE](overlays/angle),
  [Dawn](overlays/dawn), [WebRTC](overlays/webrtc), [PDFium](overlays/pdfium),
  [SwiftShader](overlays/swiftshader).

Each overlay owns its source pin, `bcr/MODULE.bazel`, metadata, versions,
overlay files, patches and presubmit. Seven planned overlays have no proposed
versions yet and cannot be staged. [overlays.json](overlays.json) records status.
See [dependency audit](docs/dependency-overlays.md) for priorities.

## Development

```sh
python3 -m unittest discover -s tests
python3 overlays/chromium/tests/validate_bcr.py
cd overlays/chromium
bazel build //:foundation
bazel test //:native_foundation_test
```

Builds and generators must use native Bazel actions. Reuse compatible BCR
dependencies. Chromium currently uses BCR Double Conversion and GoogleTest.

## Separate publication

Stage exactly one module/version per publication:

```sh
registry=$(mktemp -d)
python3 tools/stage_bcr_entry.py \
  --source-registry overlays/chromium/bcr \
  --target-registry "$registry" \
  --module chromium --version 142.0.7444.59
cd overlays/chromium/tests/bcr
bazel run --registry="file://$registry" --registry=https://bcr.bazel.build //:smoke_test
```

Output remains `modules/<module>/<version>/`, with that module's own checksums,
metadata and presubmit. Consumers continue using separate dependencies such as
`bazel_dep(name = "chromium", version = "142.0.7444.59")`.

When adding release automation, use module-specific tags `<module>/v<version>`
and release only the selected registry entry. A Chromium release must not
implicitly release V8, Skia or any other module. Published entries remain
immutable. No module has been published to BCR yet; maintainer metadata is
required before submission.

## License

Overlay scaffolding: BSD-3-Clause. Shared staging tool: Apache-2.0, adapted from
perplexityai/rocksdb. Upstream projects retain their own licenses.
