#include <dlfcn.h>

#include <cstdio>
#include <cstring>

#include "EGL/egl.h"

int main(int argc, char** argv) {
  if (argc != 3) return 1;
  void* library = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
  if (!library) {
    std::fprintf(stderr, "%s\n", dlerror());
    return 1;
  }
  void* gles = dlopen(argv[2], RTLD_NOW | RTLD_LOCAL);
  if (!gles) {
    std::fprintf(stderr, "%s\n", dlerror());
    return 1;
  }
  if (!dlsym(gles, "glClear")) return 1;
  auto query = reinterpret_cast<decltype(&eglQueryString)>(
      dlsym(library, "eglQueryString"));
  auto get = reinterpret_cast<decltype(&eglGetProcAddress)>(
      dlsym(library, "eglGetProcAddress"));
  if (!query || !get) return 1;
  const char* extensions = query(EGL_NO_DISPLAY, EGL_EXTENSIONS);
  if (!extensions || !std::strstr(extensions, "EGL_ANGLE_platform_angle") ||
      !get("glClear")) return 1;
  dlclose(gles);
  dlclose(library);
  std::puts("ANGLE client EGL/GLES dispatch passed");
  return 0;
}
