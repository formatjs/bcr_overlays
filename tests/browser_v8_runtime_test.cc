#include <unistd.h>

#include <cstdint>
#include <cstdio>
#include <memory>
#include <string>

#include "libplatform/libplatform.h"
#include "rules_cc/cc/runfiles/runfiles.h"
#include "v8.h"

#if !defined(V8_ENABLE_SANDBOX) || !defined(V8_TEMPORAL_SUPPORT) ||        \
    !defined(V8_USE_PERFETTO) || !defined(V8_USE_EXTERNAL_STARTUP_DATA) || \
    !defined(CPPGC_YOUNG_GENERATION) || !defined(DEBUG)
#error Chromium V8 profile required
#endif

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

int main(int argc, char** argv) {
  alarm(60);
  CHECK_CASE(argc == 3);
  std::string error;
  std::unique_ptr<rules_cc::cc::runfiles::Runfiles> runfiles(
      rules_cc::cc::runfiles::Runfiles::CreateForTest(&error));
  CHECK_CASE(runfiles);
  const auto icu = runfiles->Rlocation(argv[1]);
  const auto snapshot = runfiles->Rlocation(argv[2]);
  v8::V8::SetFlagsFromString("--harmony-temporal");
  CHECK_CASE(v8::V8::InitializeICUDefaultLocation(argv[0], icu.c_str()));
  v8::V8::InitializeExternalStartupDataFromFile(snapshot.c_str());
  auto platform = v8::platform::NewDefaultPlatform();
  v8::V8::InitializePlatform(platform.get());
  CHECK_CASE(v8::V8::Initialize());
  CHECK_CASE(v8::V8::IsSandboxConfiguredSecurely());
  auto* sandbox = v8::V8::GetSandboxAddressSpace();
  CHECK_CASE(sandbox && v8::V8::GetSandboxSizeInBytes() > 0);

  std::unique_ptr<v8::ArrayBuffer::Allocator> allocator(
      v8::ArrayBuffer::Allocator::NewDefaultAllocator());
  v8::Isolate::CreateParams params;
  params.array_buffer_allocator = allocator.get();
  auto* isolate = v8::Isolate::New(params);
  CHECK_CASE(isolate);
  bool passed = false;
  {
    v8::Isolate::Scope isolate_scope(isolate);
    v8::HandleScope handles(isolate);
    auto backing = v8::ArrayBuffer::NewBackingStore(isolate, 4096);
    CHECK_CASE(backing &&
               sandbox->Contains(reinterpret_cast<uintptr_t>(backing->Data())));
    auto context = v8::Context::New(isolate);
    CHECK_CASE(!context.IsEmpty());
    v8::Context::Scope context_scope(context);
    v8::TryCatch errors(isolate);
    auto source = v8::String::NewFromUtf8Literal(isolate, R"JS(
      (() => {
        const require = (value, message) => { if (!value) throw Error(message); };
        require(new Temporal.PlainDate(2024, 2, 29).add({years: 1}).toString()
                  === '2025-02-28', 'Temporal leap-day arithmetic');
        const dst = Temporal.Instant.from('2024-03-10T06:30:00Z')
            .toZonedDateTimeISO('America/New_York').add({hours: 2});
        require(dst.toString() ===
            '2024-03-10T04:30:00-04:00[America/New_York]', 'Temporal time zone');
        let rejected = false;
        try { Temporal.PlainDate.from('2023-02-29'); }
        catch (error) { rejected = error instanceof RangeError; }
        require(rejected, 'Temporal accepted invalid date');
        require(new Intl.NumberFormat('fr-FR').format(1234.5) === '1\u202f234,5',
                'Intl locale data');
        require('e\u0301'.normalize('NFC') === '\u00e9', 'Intl normalization');
        const words = [...new Intl.Segmenter('en', {granularity: 'word'})
            .segment('example.com')].map(part => part.segment).join('|');
        require(words === 'example|.|com', 'Chromium ICU word boundaries');
        require((2n ** 64n).toString() === '18446744073709551616', 'BigInt');
        const bytes = new Uint8Array([
          0, 97, 115, 109, 1, 0, 0, 0,
          1, 7, 1, 96, 2, 127, 127, 1, 127,
          3, 2, 1, 0,
          7, 7, 1, 3, 97, 100, 100, 0, 0,
          10, 9, 1, 7, 0, 32, 0, 32, 1, 106, 11
        ]);
        const wasm = new WebAssembly.Instance(new WebAssembly.Module(bytes));
        require(wasm.exports.add(20, 22) === 42, 'WebAssembly execution');
        rejected = false;
        try { new WebAssembly.Module(bytes.slice(0, -1)); }
        catch (error) { rejected = error instanceof WebAssembly.CompileError; }
        require(rejected, 'WebAssembly accepted truncated module');
        globalThis.complete = false;
        Promise.resolve(42).then(value => { globalThis.complete = value === 42; });
      })()
    )JS");
    v8::Local<v8::Script> script;
    v8::Local<v8::Value> result;
    if (v8::Script::Compile(context, source).ToLocal(&script) &&
        script->Run(context).ToLocal(&result)) {
      isolate->PerformMicrotaskCheckpoint();
      passed = context->Global()
                   ->Get(context,
                         v8::String::NewFromUtf8Literal(isolate, "complete"))
                   .ToLocal(&result) &&
               result->IsTrue();
    }
    if (errors.HasCaught()) {
      v8::String::Utf8Value message(isolate, errors.Exception());
      std::fprintf(stderr, "%s\n", *message);
    }
  }
  isolate->Dispose();
  allocator.reset();
  CHECK_CASE(v8::V8::Dispose());
  v8::V8::DisposePlatform();
  CHECK_CASE(passed);
  std::printf(
      "Chromium V8 %s: snapshot, sandbox, Temporal, Intl, Wasm passed\n",
      v8::V8::GetVersion());
  return 0;
}
