# BoringSSL Chromium PKI adapter

Existing BCR BoringSSL `0.20251002.0` snapshot, with a public Bazel target for
Chromium's PKI APIs. Proposed version: `0.20251002.0.chromium142`.

Patch adds `@boringssl//:chromium_pki` over upstream `:pki`, exporting its public
and internal PKI headers with canonical `pki/...` include paths. Upstream source
archive, compiler options and crypto/SSL targets are preserved. Compatibility
level remains 2. Googletest uses the existing Bazel 9-compatible BCR revision.

Chromium's original BoringSSL GN target includes PKI, while the selected BCR
snapshot keeps that library private. Chromium consumes PEM parsing and certificate
validation APIs from that private interface. The adapter supplies those bindings.

## Validate

From repository root:

```sh
registry=$(mktemp -d)
python3 tools/stage_bcr_entry.py --source-registry overlays/boringssl/bcr \
  --target-registry "$registry" --module boringssl --version 0.20251002.0.chromium142
cd overlays/boringssl/tests
bazel test --registry="file://$registry" --registry=https://bcr.bazel.build \
  //:pki_api_test @boringssl//:pki_test
```

Consumer test checks PEM decoding, label filtering, malformed input and duplicate
blocks. Original upstream PKI suite passes 1,280 tests. Tests register
hermeticbuild LLVM `llvm@0.8.26`; library leaves compiler selection to consumers.

No BCR publication yet; maintainers remain unset. Upstream license: Apache-2.0.
