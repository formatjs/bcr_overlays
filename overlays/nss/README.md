# NSS native Bazel overlay

NSS 3.61 with Debian `3.61-1+deb11u3` patches, matching Chromium 142's pinned
Bullseye sysroot. Proposed BCR module: `nss@3.61.deb11u3`.

`@nss//:nss` provides the Linux shared libraries, PKCS#11 modules, headers and
integrity files. Individual shared-library targets such as `:nss3`, `:nssutil3`,
`:ssl3` and `:smime3` also carry runtime modules and integrity files. Linux x86_64
supported initially.

Native C/assembly compilation, original Perl certificate-data generator, ELF
version scripts and original `shlibsign` actions. GYP resolves maintainer metadata
only; consumers invoke no GYP, Make or Ninja. Optimized crypto, FIPS mode, legacy
DBM and libpkix remain enabled. All shared libraries use one native NSPR runtime.
BCR SQLite 3.51.1.bcr.1, zlib and Perl rules supply existing dependencies.
Tests register hermeticbuild LLVM `llvm@0.8.26`; library leaves compiler selection
to consumers.

All seven Debian patches retained, including CVE-2021-43527, CVE-2022-22747 and
CVE-2023-0767 fixes. One additional patch resolves loader symlinks before locating
the companion checksum. This supports Bazel's `_solib` layout while verifying
the actual module bytes and original checksum format.

## Validate

From repository root:

```sh
registry=$(mktemp -d)
python3 tools/stage_bcr_entry.py --source-registry overlays/nspr/bcr \
  --target-registry "$registry" --module nspr --version 4.29
python3 tools/stage_bcr_entry.py --source-registry overlays/nss/bcr \
  --target-registry "$registry" --module nss --version 3.61.deb11u3
cd overlays/nss/tests
bazel test --registry="file://$registry" --registry=https://bcr.bazel.build \
  //:runtime_test //:fips_runtime_test
```

Runtime checks use real PKCS#11 modules: SHA-256, AES-GCM golden bytes and tag
rejection, RSA signing/verification, SQL and DBM key persistence across shutdown.
FIPS checks enter FIPS mode, reject weak PINs and raw secret-key imports, then
generate and use an AES key. Both modes reject changed module bytes and signatures
through the production freebl verifier.

## Regenerate metadata

Extract the pinned Mozilla source archive, apply every patch from `bcr/patches`
with `patch -p2`, then resolve the Linux graph with gyp-next 0.20.5:

```sh
python3 -m venv /tmp/nss-gyp
/tmp/nss-gyp/bin/pip install gyp-next==0.20.5
/tmp/nss-gyp/bin/python overlays/nss/tools/capture_graph.py /path/to/patched/nss \
  --gyp /tmp/nss-gyp/bin/gyp
buildifier overlays/nss/bcr/overlay/bazel/sources.bzl
```

The capture fixes platform, compiler capabilities and synthetic include paths;
114 resolved targets and 278 exported files remain auditable in `sources.bzl`.
Debian's patched `shlibsign` Makefile supplies its additional version defines.
Source pins and patch-archive checksum live in [upstream.json](upstream.json).

Upstream license: MPL-2.0. No BCR publication yet; maintainers remain unset.
Chromium crypto uses this module; full networking integration remains pending.
