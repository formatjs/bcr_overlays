# Chromium CI

`buildbuddy.yaml` cross-builds five platform bundles on hosted Linux workers.
Each successful BuildBuddy status triggers `cross-compile.yml`, which downloads
that platform's archive and SHA256 through the BuildBuddy API. It then calls
`smoke.yml` on a matching native GitHub runner. Smoke checks commit, version and
executable architecture before running the relocated browser against a local
HTTP page. No browser rebuild happens in GitHub Actions.

[Rendering checks](rendering/README.md) also compare screenshots of two local
fixtures with reviewed PNGs. Each native job preserves actual, expected and diff
images plus its rendering report, including failures.

The handoff follows [FormatJS's native smoke workflow](https://github.com/formatjs/formatjs/blob/main/.github/workflows/native-smoke.yml).
Only `buildbuddy-io[bot]` statuses with known platform names enter the handoff.
The downloader and smoke scripts come from the default branch. Downloads require
a successful, complete invocation matching the repository, commit and action;
artifact names, hosts, size and SHA256 are checked before upload to GitHub.
Separate status jobs report each native smoke result on the original commit.

Build targets use `with_cfg` to select hermetic LLVM platforms:

```sh
bazel build --config=browser //tools/ci:linux-amd64
bazel build --config=browser //tools/ci:linux-arm64
bazel build --config=browser //tools/ci:darwin-arm64
bazel build --config=browser //tools/ci:windows-amd64
bazel build --config=browser //tools/ci:windows-arm64
```

Host generators retain their execution platform. Both Windows targets use MSVC.
CI enables the approved MSVC runtime and Windows SDK license flags when fetching
their toolchains.

The linked BuildBuddy GitHub App supplies build credentials through its Bazel
wrapper. Remote cache, execution and BES use `formatjs.buildbuddy.io` with
`--config=buildbuddy`. Artifacts upload through `BUILDBUDDY_ARTIFACTS_DIRECTORY`.
GitHub downloads reuse the existing organization secret
`BUILDBUDDY_RO_PUBLIC_KEY`, already available to this repository. No new API key
or GitHub write token is needed. Pull requests build without merging the base
branch so artifact provenance matches the reported commit.

Full Chromium packaging and relocated rendering smoke pass on Linux amd64 through
BuildBuddy and native GitHub Actions. Linux ARM64 has a complete captured graph;
full compilation and native browser smoke remain in progress. All five GN graphs
are captured, including explicit Windows SDK debugger runtime inputs.

macOS ARM64 and Windows MSVC amd64/ARM64 base and Mojo executables cross-link.
`native.yml` hands those executables to native runners for allocator, JSON/files/
threads, message-pipe and shared-memory smoke checks. Full macOS and Windows
browser translation remains unfinished; component probes do not replace browser
artifact and rendering smoke.
