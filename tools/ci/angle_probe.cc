#if defined(_WIN32)
#include <windows.h>
#else
#include <dlfcn.h>
#endif

#include <cstdio>
#include <cstring>

#include "EGL/egl.h"

namespace {
#if defined(_WIN32)
using Library = HMODULE;
Library Open(const char* path) {
  return LoadLibraryExA(path, nullptr, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR |
                                         LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
}
auto Symbol(Library library, const char* name) {
  return GetProcAddress(library, name);
}
void Close(Library library) { FreeLibrary(library); }
void ReportError() { std::fprintf(stderr, "LoadLibrary: %lu\n", GetLastError()); }
#else
using Library = void*;
Library Open(const char* path) { return dlopen(path, RTLD_NOW | RTLD_LOCAL); }
auto Symbol(Library library, const char* name) { return dlsym(library, name); }
void Close(Library library) { dlclose(library); }
void ReportError() { std::fprintf(stderr, "%s\n", dlerror()); }
#endif
}  // namespace

int main(int argc, char** argv) {
  if (argc != 3) return 1;
  Library library = Open(argv[1]);
  if (!library) {
    ReportError();
    return 1;
  }
  Library gles = Open(argv[2]);
  if (!gles) {
    ReportError();
    return 1;
  }
  if (!Symbol(gles, "glClear")) return 1;
  auto query = reinterpret_cast<decltype(&eglQueryString)>(
      Symbol(library, "eglQueryString"));
  auto get = reinterpret_cast<decltype(&eglGetProcAddress)>(
      Symbol(library, "eglGetProcAddress"));
  if (!query || !get) return 1;
  const char* extensions = query(EGL_NO_DISPLAY, EGL_EXTENSIONS);
  if (!extensions || !std::strstr(extensions, "EGL_ANGLE_platform_angle") ||
      !get("glClear")) return 1;
  Close(gles);
  Close(library);
  std::puts("ANGLE client EGL/GLES dispatch passed");
  return 0;
}
