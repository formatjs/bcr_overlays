#include <windows.h>

#include <cstdio>
#include <cstring>
#include <cwchar>

#include "dxc/dxcapi.h"

int main() {
  wchar_t path[32768];
  DWORD length = GetModuleFileNameW(nullptr, path, 32768);
  if (!length || length == 32768) return 1;
  wchar_t* filename = std::wcsrchr(path, L'\\');
  if (!filename || filename - path + 16 >= 32768) return 1;
  constexpr wchar_t name[] = L"dxcompiler.dll";
  std::wmemcpy(filename + 1, name, sizeof(name) / sizeof(wchar_t));
  HMODULE library = LoadLibraryExW(
      path, nullptr,
      LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
  if (!library) {
    std::fprintf(stderr, "dxcompiler.dll load failed: %lu\n", GetLastError());
    return 1;
  }
  auto create = reinterpret_cast<DxcCreateInstanceProc>(
      GetProcAddress(library, "DxcCreateInstance"));
  IDxcCompiler3* compiler = nullptr;
  if (!create || FAILED(create(CLSID_DxcCompiler, IID_PPV_ARGS(&compiler)))) {
    return 1;
  }
  constexpr char shader[] = R"(
RWStructuredBuffer<uint> values : register(u0);
[numthreads(4, 1, 1)]
void main(uint3 id : SV_DispatchThreadID) {
  values[id.x] = id.x * 3u + 7u;
}
)";
  DxcBuffer source{shader, sizeof(shader) - 1, DXC_CP_UTF8};
  const wchar_t* arguments[] = {L"-E", L"main", L"-T", L"cs_6_0", L"-Vd"};
  IDxcResult* result = nullptr;
  if (FAILED(compiler->Compile(&source, arguments, 5, nullptr,
                               IID_PPV_ARGS(&result)))) return 1;
  HRESULT status = E_FAIL;
  result->GetStatus(&status);
  if (FAILED(status)) {
    IDxcBlobUtf8* errors = nullptr;
    result->GetOutput(DXC_OUT_ERRORS, IID_PPV_ARGS(&errors), nullptr);
    if (errors) std::fprintf(stderr, "%s\n", errors->GetStringPointer());
    return 1;
  }
  IDxcBlob* object = nullptr;
  if (FAILED(result->GetOutput(DXC_OUT_OBJECT, IID_PPV_ARGS(&object), nullptr)) ||
      !object || object->GetBufferSize() < 32 ||
      std::memcmp(object->GetBufferPointer(), "DXBC", 4) != 0) return 1;
  std::printf("DXC compiled HLSL into %zu-byte DXIL container\n",
              object->GetBufferSize());
  object->Release();
  result->Release();
  compiler->Release();
  FreeLibrary(library);
  return 0;
}
