#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES2/gl2.h>
#include <dlfcn.h>
#include <pci/pci.h>
#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <memory>
#include <string>

#include "rules_cc/cc/runfiles/runfiles.h"

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

int main(int argc, char** argv) {
  CHECK_CASE(argc == 4);
  std::string error;
  std::unique_ptr<rules_cc::cc::runfiles::Runfiles> runfiles(
      rules_cc::cc::runfiles::Runfiles::CreateForTest(&error));
  CHECK_CASE(runfiles);
  unsetenv("VK_DRIVER_FILES");
  unsetenv("VK_ADD_DRIVER_FILES");
  unsetenv("VK_ICD_FILENAMES");
  unsetenv("VK_INSTANCE_LAYERS");
  CHECK_CASE(setenv("VK_LOADER_LAYERS_DISABLE", "~implicit~", 1) == 0);
  void* gles =
      dlopen(runfiles->Rlocation(argv[2]).c_str(), RTLD_NOW | RTLD_LOCAL);
  if (!gles)
    std::fprintf(stderr, "%s\n", dlerror());
  CHECK_CASE(gles);
  auto native_pci_alloc =
      reinterpret_cast<decltype(&pci_alloc)>(dlsym(gles, "pci_alloc"));
  CHECK_CASE(native_pci_alloc);
  Dl_info pci_location{};
  CHECK_CASE(dladdr(reinterpret_cast<void*>(native_pci_alloc), &pci_location));
  CHECK_CASE(pci_location.dli_fname &&
             std::filesystem::equivalent(pci_location.dli_fname,
                                         runfiles->Rlocation(argv[3])));
  auto filter_init = reinterpret_cast<decltype(&pci_filter_init)>(
      dlsym(gles, "pci_filter_init"));
  auto filter_parse = reinterpret_cast<decltype(&pci_filter_parse_slot)>(
      dlsym(gles, "pci_filter_parse_slot"));
  CHECK_CASE(filter_init && filter_parse);
  pci_filter filter;
  filter_init(nullptr, &filter);
  char slot[] = "0000:00:01.0";
  CHECK_CASE(filter_parse(&filter, slot) == nullptr);
  CHECK_CASE(filter.domain == 0 && filter.bus == 0 && filter.slot == 1 &&
             filter.func == 0);
  char invalid_slot[] = "not-a-slot";
  CHECK_CASE(filter_parse(&filter, invalid_slot) != nullptr);
  void* egl =
      dlopen(runfiles->Rlocation(argv[1]).c_str(), RTLD_NOW | RTLD_LOCAL);
  if (!egl)
    std::fprintf(stderr, "%s\n", dlerror());
  CHECK_CASE(egl);
#define EGL_FUNCTION(name, type)                         \
  auto name = reinterpret_cast<type>(dlsym(egl, #name)); \
  CHECK_CASE(name)
  EGL_FUNCTION(eglGetProcAddress, PFNEGLGETPROCADDRESSPROC);
  EGL_FUNCTION(eglInitialize, PFNEGLINITIALIZEPROC);
  EGL_FUNCTION(eglChooseConfig, PFNEGLCHOOSECONFIGPROC);
  EGL_FUNCTION(eglCreatePbufferSurface, PFNEGLCREATEPBUFFERSURFACEPROC);
  EGL_FUNCTION(eglCreateContext, PFNEGLCREATECONTEXTPROC);
  EGL_FUNCTION(eglMakeCurrent, PFNEGLMAKECURRENTPROC);
  EGL_FUNCTION(eglDestroySurface, PFNEGLDESTROYSURFACEPROC);
  EGL_FUNCTION(eglDestroyContext, PFNEGLDESTROYCONTEXTPROC);
  EGL_FUNCTION(eglTerminate, PFNEGLTERMINATEPROC);
#undef EGL_FUNCTION
  auto get_platform = reinterpret_cast<PFNEGLGETPLATFORMDISPLAYEXTPROC>(
      eglGetProcAddress("eglGetPlatformDisplayEXT"));
  CHECK_CASE(get_platform);
  const EGLint display_attributes[] = {
      EGL_PLATFORM_ANGLE_TYPE_ANGLE, EGL_PLATFORM_ANGLE_TYPE_VULKAN_ANGLE,
      EGL_PLATFORM_ANGLE_DEVICE_TYPE_ANGLE,
      EGL_PLATFORM_ANGLE_DEVICE_TYPE_SWIFTSHADER_ANGLE, EGL_NONE};
  EGLDisplay display = get_platform(EGL_PLATFORM_ANGLE_ANGLE,
                                    EGL_DEFAULT_DISPLAY, display_attributes);
  CHECK_CASE(display != EGL_NO_DISPLAY);
  EGLint major = 0, minor = 0;
  CHECK_CASE(eglInitialize(display, &major, &minor));
  CHECK_CASE(major == 1 && minor >= 4);
  const EGLint config_attributes[] = {EGL_SURFACE_TYPE,
                                      EGL_PBUFFER_BIT,
                                      EGL_RENDERABLE_TYPE,
                                      EGL_OPENGL_ES2_BIT,
                                      EGL_RED_SIZE,
                                      8,
                                      EGL_GREEN_SIZE,
                                      8,
                                      EGL_BLUE_SIZE,
                                      8,
                                      EGL_ALPHA_SIZE,
                                      8,
                                      EGL_NONE};
  EGLConfig config;
  EGLint count = 0;
  CHECK_CASE(eglChooseConfig(display, config_attributes, &config, 1, &count));
  CHECK_CASE(count == 1);
  const EGLint pbuffer_attributes[] = {EGL_WIDTH, 4, EGL_HEIGHT, 4, EGL_NONE};
  EGLSurface surface =
      eglCreatePbufferSurface(display, config, pbuffer_attributes);
  CHECK_CASE(surface != EGL_NO_SURFACE);
  const EGLint context_attributes[] = {EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE};
  EGLContext context =
      eglCreateContext(display, config, EGL_NO_CONTEXT, context_attributes);
  CHECK_CASE(context != EGL_NO_CONTEXT);
  CHECK_CASE(eglMakeCurrent(display, surface, surface, context));
#define GL_FUNCTION(name, type)                                 \
  auto name = reinterpret_cast<type>(eglGetProcAddress(#name)); \
  CHECK_CASE(name)
  GL_FUNCTION(glGetString, PFNGLGETSTRINGPROC);
  GL_FUNCTION(glClearColor, PFNGLCLEARCOLORPROC);
  GL_FUNCTION(glClear, PFNGLCLEARPROC);
  GL_FUNCTION(glReadPixels, PFNGLREADPIXELSPROC);
  GL_FUNCTION(glGetError, PFNGLGETERRORPROC);
  GL_FUNCTION(glCreateShader, PFNGLCREATESHADERPROC);
  GL_FUNCTION(glShaderSource, PFNGLSHADERSOURCEPROC);
  GL_FUNCTION(glCompileShader, PFNGLCOMPILESHADERPROC);
  GL_FUNCTION(glGetShaderiv, PFNGLGETSHADERIVPROC);
  GL_FUNCTION(glDeleteShader, PFNGLDELETESHADERPROC);
  GL_FUNCTION(glCreateProgram, PFNGLCREATEPROGRAMPROC);
  GL_FUNCTION(glAttachShader, PFNGLATTACHSHADERPROC);
  GL_FUNCTION(glBindAttribLocation, PFNGLBINDATTRIBLOCATIONPROC);
  GL_FUNCTION(glLinkProgram, PFNGLLINKPROGRAMPROC);
  GL_FUNCTION(glGetProgramiv, PFNGLGETPROGRAMIVPROC);
  GL_FUNCTION(glUseProgram, PFNGLUSEPROGRAMPROC);
  GL_FUNCTION(glDeleteProgram, PFNGLDELETEPROGRAMPROC);
  GL_FUNCTION(glViewport, PFNGLVIEWPORTPROC);
  GL_FUNCTION(glVertexAttribPointer, PFNGLVERTEXATTRIBPOINTERPROC);
  GL_FUNCTION(glEnableVertexAttribArray, PFNGLENABLEVERTEXATTRIBARRAYPROC);
  GL_FUNCTION(glDrawArrays, PFNGLDRAWARRAYSPROC);
#undef GL_FUNCTION
  const char* renderer =
      reinterpret_cast<const char*>(glGetString(GL_RENDERER));
  CHECK_CASE(renderer && std::strstr(renderer, "SwiftShader"));
  std::fprintf(stdout, "%s\n", renderer);
  const char* vertex_source =
      "attribute vec2 position; void main() { gl_Position = vec4(position, 0, "
      "1); }";
  const char* fragment_source =
      "precision mediump float; void main() { gl_FragColor = vec4(0, 1, 0, 1); "
      "}";
  GLuint vertex = glCreateShader(GL_VERTEX_SHADER);
  GLuint fragment = glCreateShader(GL_FRAGMENT_SHADER);
  CHECK_CASE(vertex && fragment);
  glShaderSource(vertex, 1, &vertex_source, nullptr);
  glShaderSource(fragment, 1, &fragment_source, nullptr);
  glCompileShader(vertex);
  glCompileShader(fragment);
  GLint status = GL_FALSE;
  glGetShaderiv(vertex, GL_COMPILE_STATUS, &status);
  CHECK_CASE(status == GL_TRUE);
  glGetShaderiv(fragment, GL_COMPILE_STATUS, &status);
  CHECK_CASE(status == GL_TRUE);
  GLuint program = glCreateProgram();
  CHECK_CASE(program);
  glAttachShader(program, vertex);
  glAttachShader(program, fragment);
  glBindAttribLocation(program, 0, "position");
  glLinkProgram(program);
  glGetProgramiv(program, GL_LINK_STATUS, &status);
  CHECK_CASE(status == GL_TRUE);
  glUseProgram(program);
  glViewport(0, 0, 4, 4);
  const std::array<GLfloat, 6> vertices = {-1, -1, 3, -1, -1, 3};
  glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, vertices.data());
  glEnableVertexAttribArray(0);
  glClearColor(1, 0, 0, 1);
  glClear(GL_COLOR_BUFFER_BIT);
  glDrawArrays(GL_TRIANGLES, 0, 3);
  std::array<unsigned char, 4 * 4 * 4> pixels{};
  glReadPixels(0, 0, 4, 4, GL_RGBA, GL_UNSIGNED_BYTE, pixels.data());
  CHECK_CASE(glGetError() == GL_NO_ERROR);
  for (size_t i = 0; i < pixels.size(); i += 4) {
    CHECK_CASE(pixels[i] == 0 && pixels[i + 1] == 255 && pixels[i + 2] == 0 &&
               pixels[i + 3] == 255);
  }
  glUseProgram(0);
  glDeleteProgram(program);
  glDeleteShader(vertex);
  glDeleteShader(fragment);
  GLuint shader = glCreateShader(GL_FRAGMENT_SHADER);
  CHECK_CASE(shader);
  const char* invalid = "void main() { invalid shader; }";
  glShaderSource(shader, 1, &invalid, nullptr);
  glCompileShader(shader);
  GLint compiled = GL_TRUE;
  glGetShaderiv(shader, GL_COMPILE_STATUS, &compiled);
  CHECK_CASE(compiled == GL_FALSE);
  glDeleteShader(shader);
  CHECK_CASE(glGetError() == GL_NO_ERROR);
  CHECK_CASE(
      eglMakeCurrent(display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT));
  CHECK_CASE(eglDestroyContext(display, context));
  CHECK_CASE(eglDestroySurface(display, surface));
  CHECK_CASE(eglTerminate(display));
  CHECK_CASE(dlclose(egl) == 0);
  CHECK_CASE(dlclose(gles) == 0);
  return 0;
}
