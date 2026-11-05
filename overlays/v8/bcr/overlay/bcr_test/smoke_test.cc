#include <iostream>
#include <memory>

#include "libplatform/libplatform.h"
#include "v8.h"

int main(int argc, char** argv) {
  if (!v8::V8::InitializeICUDefaultLocation(argv[0])) return 1;
  v8::V8::InitializeExternalStartupData(argv[0]);
  auto platform = v8::platform::NewDefaultPlatform();
  v8::V8::InitializePlatform(platform.get());
  if (!v8::V8::Initialize()) return 1;

  std::unique_ptr<v8::ArrayBuffer::Allocator> allocator(
      v8::ArrayBuffer::Allocator::NewDefaultAllocator());
  v8::Isolate::CreateParams params;
  params.array_buffer_allocator = allocator.get();
  auto* isolate = v8::Isolate::New(params);
  bool passed = false;
  {
    v8::Isolate::Scope isolate_scope(isolate);
    v8::HandleScope handles(isolate);
    auto context = v8::Context::New(isolate);
    v8::Context::Scope context_scope(context);
    v8::TryCatch errors(isolate);
    auto source = v8::String::NewFromUtf8Literal(isolate,
#ifdef EXPECT_INTL
      R"JS(
        if (typeof Intl !== 'object') throw Error('Intl missing');
        if (new Intl.NumberFormat('fr-FR').format(1234.5).indexOf(',') < 0)
          throw Error('Intl locale data missing');
        if ('e\u0301'.normalize('NFC') !== '\u00e9')
          throw Error('Intl normalization failed');
        const boundaries = [...new Intl.Segmenter('en', {granularity: 'word'})
          .segment('example.com')].map(part => part.segment).join('|');
        if (boundaries !== 'example|.|com')
          throw Error('Chromium word-break patch missing');
      )JS"
#endif
      R"JS(
      (() => {
        function fib(n) { return n < 2 ? n : fib(n - 1) + fib(n - 2); }
        if (fib(12) !== 144) throw Error('JavaScript execution failed');
        if ((2n ** 64n).toString() !== '18446744073709551616')
          throw Error('BigInt failed');
        for (const number of [Number.MIN_VALUE, Number.MAX_VALUE, 0.1,
                              1.2345678901234567, 1e-100, -1e100]) {
          if (Number(String(number)) !== number)
            throw Error('decimal conversion failed');
        }
        if (!Object.is(Number('-0'), -0) || Number('1e999') !== Infinity)
          throw Error('decimal edge case failed');
        const half = new Float16Array([1.00048828125, 65504, 2 ** -24]);
        if (half[0] !== 1 || half[1] !== 65504 || half[2] !== 2 ** -24)
          throw Error('FP16 rounding failed');
        if ('\ud800'.toWellFormed() !== '\ufffd' ||
            Uint8Array.fromBase64('8J+agA==').join(',') !== '240,159,154,128')
          throw Error('Unicode conversion failed');
        const bytes = new Uint8Array([
          0, 97, 115, 109, 1, 0, 0, 0,
          1, 7, 1, 96, 2, 127, 127, 1, 127,
          3, 2, 1, 0,
          7, 7, 1, 3, 97, 100, 100, 0, 0,
          10, 9, 1, 7, 0, 32, 0, 32, 1, 106, 11
        ]);
        const wasm = new WebAssembly.Instance(new WebAssembly.Module(bytes));
        if (wasm.exports.add(20, 22) !== 42) throw Error('WebAssembly failed');
        const view = new Uint32Array(new ArrayBuffer(8));
        view[1] = 0x12345678;
        if (view[1] !== 0x12345678) throw Error('ArrayBuffer failed');
        globalThis.result = false;
        Promise.resolve(42).then(value => { globalThis.result = value === 42; });
      })()
    )JS");
    v8::Local<v8::Script> script;
    v8::Local<v8::Value> result;
    if (v8::Script::Compile(context, source).ToLocal(&script) &&
        script->Run(context).ToLocal(&result)) {
      isolate->PerformMicrotaskCheckpoint();
      if (context->Global()
              ->Get(context, v8::String::NewFromUtf8Literal(isolate, "result"))
              .ToLocal(&result)) {
        passed = result->IsTrue();
      }
    }
    if (errors.HasCaught()) {
      v8::String::Utf8Value message(isolate, errors.Exception());
      std::cerr << *message << '\n';
    }
  }
  isolate->Dispose();
  v8::V8::Dispose();
  v8::V8::DisposePlatform();
  if (!passed) return 1;
  std::cout << "V8 " << v8::V8::GetVersion()
            << ": JavaScript, BigInt, WebAssembly, buffers, microtasks passed\n";
  return 0;
}
