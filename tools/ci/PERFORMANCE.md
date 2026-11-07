# Chromium build performance

Optimize measured compiler work first. Keep compiler flags, target ABIs, and
artifact smoke coverage intact. Compare the same workload and cache state;
registered actions are not executed compiles.

## Cold-build target

Target: under one hour per supported triple on BuildBuddy, including artifact
packaging. Preserve hermetic toolchains, declared inputs, compiler options,
target ABIs, and native rendering smoke coverage. No successful cold result has
been established. The user's observed build effort, including retries, is about
2.5 hours; the mixed-cache profile below is not a cold baseline.

Measure with fresh Bazel output state and action-cache reuse disabled. Record
repository/download cache state and shared RBE CAS conditions; a fresh client
does not make the remote CAS cold. Report fetch/setup, analysis, execution,
linking, and packaging separately, plus total elapsed time and retries. Do not
sum overlapping profile spans as wall time. Confirm executed compiler counts
before calling a run cold.

Current scanner coverage has a host gap: Linux ARM64's browser capture contains
19 host Blink-core libraries with 2,733 source entries outside the dedicated
Blink-core macro. Validate these compiler contexts separately before extending
scanning. The other four browser captures contain no Blink-core libraries.

The hosted build command accepts `--cold`. It starts a batch Bazel process with
a unique output root and fresh repository download cache, disables disk caches
and remote action-cache reads, and writes `cold-build.json` even on failure.
Successful results require actual C++ executions, complete cache metrics, and
zero observed action-cache hits. Elapsed time includes artifact copying but
excludes temporary-directory cleanup. Shared remote CAS remains populated.

Each `perf/cold-<platform>` branch triggers only that platform's cold browser
job. Run sequentially after the regular browser and throughput trials finish;
do not report shared-load experiments as controlled concurrency comparisons.

## Baseline

[Linux ARM64 compile-heavy profile](https://formatjs.buildbuddy.io/invocation/97238e03-06be-49ad-abed-4699731fe294):

- 57m32s wall time; 49s analysis, 56m35s execution.
- 18,337 remote executions; 16,589 remote cache hits. Mixed cache, not fully cold.
  This run failed at the snapshot-generator link, so it is not a successful
  browser build-time estimate.
- 17,849 recorded C++ worker spans. Blink accounts for 8,852 spans and 55,293
  worker-seconds; 8,833 Blink spans compile host tools.
- Merkle construction: 27,533 concurrent task-seconds. Client CPU averages 10.54
  cores; worker queue time is small. These sums overlap and are not wall time.
- Slowest recorded compiler: `layout_box.cc`, 86.1s worker time.
- Current representative Blink action declares 76,130 inputs; compilation
  context exposes 74,982 headers.

## Order of work

1. **Reduce compiler inputs.** The isolated Blink probe uses the real compilation
   context and compiler options. Compare compact execution logs, compiler-only
   timing, and archive hashes. Include scanning needs both its Bazel flag and
   requested feature. If this reduces inputs, repeat representative compiles,
   then validate all five browser builds and native rendering smoke tests.
2. **Share host objects through a narrow dependency seam.** Confirm compiler,
   defines, headers, ABI, and link dependencies match. Measure the complete host
   closure before rollout. Avoid aliases that import additional native closures.
3. **Tune client resources and concurrency.** After input work, compare fixed
   compile workloads at different client CPU allocations and action concurrency.
   Record wall time, client CPU, heap, GC, and actual remote executions. Increasing
   remote concurrency alone does not fix client input-processing saturation.

Also audit include-directory propagation. The representative core target has
14 captured include directories but resolves 945 search entries through its
dependency context. Captured target-local directories may belong in local
compiler options rather than public `includes`; validate header selection and
object equivalence before changing that boundary.

## Results so far

- Payload compression now caches independently of revision stamping. A real
  Windows payload took 138.6s to compress; subsequent stamps took 5.7s and 1.3s.
  This improves packaging, not compiler throughput.
- Rejected host-Mojo sharing: 21 aliases removed 353 source entries locally but
  grew the full registered C++ graph from 83,734 to 84,278 actions. Reverted.
- First compact-log scanner comparison produced identical archives but zero
  input reduction. Compiler action times were 31.2s and 21.8s; one pair does not
  establish a speedup. The required feature was missing. Corrected pilot runs
  separately from production browser settings.
- Global scanner features broke hermetic LLVM's glibc bootstrap (`config.h`
  missing). The next pilot requests the feature only on its Blink probe; baseline
  still disables the scanner flag. Toolchain dependencies keep their existing
  feature selection.
- [Scoped single-source pilot](https://formatjs.buildbuddy.io/invocation/8520913d-1109-4677-aad6-3f3b69406c47)
  passed with identical archive bytes: 72,405 input paths removed, 338 added,
  **72,067 fewer paths net**. Macro-selected Skia headers and a directory needed
  by its relative include remain mandatory inputs. Action time was 27.0s versus
  23.6s; worker time 23.7s versus 22.6s. This pair does not establish a full-build
  speedup. The next experiment covers layout, view, and SVG paint sources in
  baseline/scanner/scanner/baseline order, forcing recompilation each time.
- [Repeated three-source benchmark](https://formatjs.buildbuddy.io/invocation/555bc229-3711-450c-9621-3fb29d9fec5e)
  passed all four runs with identical archive bytes. Both paired comparisons
  removed 219,959 paths and added 987: **218,972 fewer compiler input paths**
  across three actions. Whole-probe wall times were baseline 59.1s/45.3s and
  scanner 47.4s/44.1s. The first baseline also executed two extra remote actions;
  worker load was uncontrolled. Input reduction repeats; browser wall-time
  improvement remains unmeasured. Production scanning remains off until wider
  source and cross-platform validation passes.

The cross-platform archive pilot also passes on Darwin ARM64 with debug info
enabled: 208,487 paths removed and 486 added, or 208,001 fewer paths per comparison
across three actions. All four archive hashes match. The first Darwin attempt
exposed an unwanted dynamic-library link; probes now explicitly use static
archives, matching the owning Chromium libraries.

The full-browser candidate requests scanning only for Blink core libraries and
keeps the known macro-selected Skia headers mandatory. Its rollout gate includes
all five browser artifacts, native rendering smoke, and the Linux runtime suite.
BuildBuddy profiles must distinguish include discovery and repository setup from
compiler worker time before claiming a wall-time improvement.

Keep raw profiles in BuildBuddy or local temporary files. GitHub artifacts carry
sanitized metrics only.
