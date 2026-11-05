#include <dlfcn.h>
#include <glib-object.h>
#include <unistd.h>

#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <memory>
#include <string>
#include <system_error>
#include <utility>

#include "base/at_exit.h"
#include "base/base_paths.h"
#include "base/command_line.h"
#include "base/files/file_path.h"
#include "base/memory/ref_counted.h"
#include "base/native_library.h"
#include "base/path_service.h"
#include "base/task/single_thread_task_executor.h"
#include "base/task/thread_pool/thread_pool_instance.h"
#include "rules_cc/cc/runfiles/runfiles.h"
#include "ui/gl/gl_bindings.h"
#include "ui/gl/gl_context_egl.h"
#include "ui/gl/gl_display_manager.h"
#include "ui/gl/gl_egl_api_implementation.h"
#include "ui/gl/gl_gl_api_implementation.h"
#include "ui/gl/gl_implementation.h"
#include "ui/gl/gl_surface_egl.h"
#include "ui/gl/init/gl_factory.h"
#include "ui/ozone/public/ozone_platform.h"

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

int main(int argc, char** argv) {
  base::AtExitManager at_exit;
  base::CommandLine::Init(argc, argv);
  base::SingleThreadTaskExecutor executor;
  base::ThreadPoolInstance::CreateAndStartWithDefaultParams("ChromiumGL");
  alarm(30);
  CHECK_CASE(argc == 5 || (argc == 6 && std::strcmp(argv[5], "--ozone") == 0));
  const bool use_ozone = argc == 6;
  std::string error;
  std::unique_ptr<rules_cc::cc::runfiles::Runfiles> runfiles(
      rules_cc::cc::runfiles::Runfiles::CreateForTest(&error));
  CHECK_CASE(runfiles);
  for (auto [symbol, index] : std::array<std::pair<const char*, int>, 2>{
           {{"g_hash_table_new", 3}, {"g_type_register_static", 4}}}) {
    void* address = dlsym(RTLD_DEFAULT, symbol);
    Dl_info location{};
    CHECK_CASE(address && dladdr(address, &location) && location.dli_fname);
    std::error_code status;
    CHECK_CASE(std::filesystem::equivalent(location.dli_fname,
                                           runfiles->Rlocation(argv[index]),
                                           status) &&
               !status);
  }
  auto* object = G_OBJECT(g_object_new(G_TYPE_OBJECT, nullptr));
  CHECK_CASE(object);
  g_object_set_data_full(object, "native-bazel", g_strdup("shared-glib"),
                         g_free);
  CHECK_CASE(std::strcmp(static_cast<const char*>(
                             g_object_get_data(object, "native-bazel")),
                         "shared-glib") == 0);
  g_object_unref(object);

  unsetenv("VK_DRIVER_FILES");
  unsetenv("VK_ADD_DRIVER_FILES");
  unsetenv("VK_ICD_FILENAMES");
  unsetenv("VK_INSTANCE_LAYERS");
  unsetenv("DISPLAY");
  CHECK_CASE(setenv("VK_LOADER_LAYERS_DISABLE", "~implicit~", 1) == 0);
  gl::GLDisplayEGL* display = nullptr;
  scoped_refptr<gl::GLSurface> surface;
  scoped_refptr<gl::GLContext> context;
  gl::GLContextAttribs attributes;
  if (use_ozone) {
    auto* command_line = base::CommandLine::ForCurrentProcess();
    command_line->AppendSwitchASCII("ozone-platform", "headless");
    command_line->AppendSwitchASCII("use-gl", "angle");
    command_line->AppendSwitchASCII("use-angle", "swiftshader");
    CHECK_CASE(base::PathService::Override(
        base::DIR_MODULE,
        base::FilePath(runfiles->Rlocation(argv[1])).DirName()));
    ui::OzonePlatform::InitParams params;
    params.single_process = true;
    CHECK_CASE(ui::OzonePlatform::InitializeForUI(params));
    ui::OzonePlatform::InitializeForGPU(params);
    CHECK_CASE(ui::OzonePlatform::IsInitialized());
    CHECK_CASE(ui::OzonePlatform::GetPlatformNameForTest() == "headless");
    auto* initialized =
        gl::init::InitializeGLOneOff(gl::GpuPreference::kDefault);
    CHECK_CASE(initialized);
    display = initialized->GetAs<gl::GLDisplayEGL>();
    CHECK_CASE(display && display->IsInitialized() &&
               display->GetDisplayType() == gl::ANGLE_SWIFTSHADER);
    surface = gl::init::CreateOffscreenGLSurface(display, gfx::Size(4, 4));
    CHECK_CASE(surface);
    context = gl::init::CreateGLContext(nullptr, surface.get(), attributes);
    CHECK_CASE(context);
  } else {
    auto gles = base::LoadNativeLibrary(
        base::FilePath(runfiles->Rlocation(argv[2])), nullptr);
    auto egl = base::LoadNativeLibrary(
        base::FilePath(runfiles->Rlocation(argv[1])), nullptr);
    CHECK_CASE(gles && egl);
    gl::AddGLNativeLibrary(gles);
    gl::AddGLNativeLibrary(egl);
    gl::SetGLGetProcAddressProc(reinterpret_cast<gl::GLGetProcAddressProc>(
        base::GetFunctionPointerFromNativeLibrary(egl, "eglGetProcAddress")));
    gl::SetGLImplementationParts(
        gl::GLImplementationParts(gl::ANGLEImplementation::kSwiftShader));
    gl::InitializeStaticGLBindingsGL();
    gl::InitializeStaticGLBindingsEGL();
    display = gl::GLDisplayManager<gl::GLDisplayEGL>::GetInstance()->GetDisplay(
        gl::GpuPreference::kDefault);
    CHECK_CASE(display->Initialize(
        true, {gl::ANGLE_SWIFTSHADER},
        gl::EGLDisplayPlatform(EGL_DEFAULT_DISPLAY,
                               EGL_PLATFORM_SURFACELESS_MESA)));
    CHECK_CASE(display->IsInitialized() &&
               display->GetDisplayType() == gl::ANGLE_SWIFTSHADER);
    surface =
        base::MakeRefCounted<gl::PbufferGLSurfaceEGL>(display, gfx::Size(4, 4));
    CHECK_CASE(surface->Initialize(gl::GLSurfaceFormat()));
    context = base::MakeRefCounted<gl::GLContextEGL>(nullptr);
    CHECK_CASE(attributes.client_major_es_version == 3 &&
               !attributes.can_skip_validation);
    CHECK_CASE(context->Initialize(surface.get(), attributes));
  }
  CHECK_CASE(context->MakeCurrent(surface.get()));
  CHECK_CASE(gl::GLContext::GetCurrent() == context.get());
  const char* renderer =
      reinterpret_cast<const char*>(glGetString(GL_RENDERER));
  CHECK_CASE(renderer && std::strstr(renderer, "SwiftShader"));
  std::printf("Chromium GL: %s\n", renderer);
  const char* vertex_source =
      "#version 300 es\nin vec2 position; void main() { gl_Position = "
      "vec4(position, 0, 1); }";
  const char* fragment_source =
      "#version 300 es\nprecision mediump float; out vec4 color; void main() { "
      "color = vec4(0, 1, 0, 1); }";
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
  glAttachShader(program, vertex);
  glAttachShader(program, fragment);
  glBindAttribLocation(program, 0, "position");
  glLinkProgram(program);
  glGetProgramiv(program, GL_LINK_STATUS, &status);
  CHECK_CASE(status == GL_TRUE);
  glUseProgram(program);
  GLuint buffer = 0;
  glGenBuffersARB(1, &buffer);
  glBindBuffer(GL_ARRAY_BUFFER, buffer);
  const std::array<GLfloat, 6> vertices = {-1, -1, 3, -1, -1, 3};
  glBufferData(GL_ARRAY_BUFFER, sizeof(vertices), vertices.data(),
               GL_STATIC_DRAW);
  glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, nullptr);
  glEnableVertexAttribArray(0);
  glViewport(0, 0, 4, 4);
  glClearColor(1, 0, 0, 1);
  glClear(GL_COLOR_BUFFER_BIT);
  glDrawArrays(GL_TRIANGLES, 0, 3);
  std::array<unsigned char, 64> pixels{};
  glReadPixels(0, 0, 4, 4, GL_RGBA, GL_UNSIGNED_BYTE, pixels.data());
  CHECK_CASE(glGetError() == GL_NO_ERROR);
  for (size_t i = 0; i < pixels.size(); i += 4) {
    CHECK_CASE(pixels[i] == 0 && pixels[i + 1] == 255 && pixels[i + 2] == 0 &&
               pixels[i + 3] == 255);
  }
  glDeleteBuffersARB(1, &buffer);
  glUseProgram(0);
  glDeleteProgram(program);
  glDeleteShader(vertex);
  glDeleteShader(fragment);
  CHECK_CASE(glGetError() == GL_NO_ERROR);
  context->ReleaseCurrent(surface.get());
  context.reset();
  surface.reset();
  if (use_ozone) {
    gl::init::ShutdownGL(display, false);
  } else {
    display->Shutdown();
    gl::ClearBindingsGL();
    gl::ClearBindingsEGL();
    gl::UnloadGLNativeLibraries(false);
  }
  base::ThreadPoolInstance::Get()->Shutdown();
  return 0;
}
