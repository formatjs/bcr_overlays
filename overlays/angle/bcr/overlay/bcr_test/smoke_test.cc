#include <iostream>
#include <string>

#include "GLES3/gl3.h"
#include "GLSLANG/ShaderLang.h"
#include "common/angle_version_info.h"

bool CheckCompiler(ShShaderOutput output) {
  ShBuiltInResources resources;
  sh::InitBuiltInResources(&resources);
  ShHandle compiler = sh::ConstructCompiler(GL_FRAGMENT_SHADER, SH_WEBGL2_SPEC,
                                            output, &resources);
  if (!compiler) return false;
  ShCompileOptions options;
  options.objectCode = true;
  const char* valid = R"GLSL(#version 300 es
    precision mediump float;
    out vec4 color;
    void main() { color = vec4(1.0, 0.5, 0.0, 1.0); }
  )GLSL";
  bool passed = sh::Compile(compiler, &valid, 1, options) &&
                sh::GetShaderVersion(compiler) == 300 &&
                sh::GetObjectCode(compiler).find("main") != std::string::npos;
  if (!passed) std::cerr << sh::GetInfoLog(compiler) << '\n';

  const char* invalid = R"GLSL(#version 300 es
    precision mediump float;
    out vec4 color;
    void main() { color = missing_variable; }
  )GLSL";
  passed = passed && !sh::Compile(compiler, &invalid, 1, options) &&
           !sh::GetInfoLog(compiler).empty();
  sh::Destruct(compiler);
  return passed;
}

int main() {
  if (!sh::Initialize()) return 1;
  bool passed = CheckCompiler(SH_ESSL_OUTPUT) &&
                CheckCompiler(SH_GLSL_330_CORE_OUTPUT);
  passed = passed && std::string(angle::GetANGLECommitHash()) == "e5b338502c7c";
  if (!sh::Finalize() || !passed) return 1;
  std::cout << "ANGLE: ESSL/GLSL translation, invalid shader rejection, source pin passed\n";
  return 0;
}
