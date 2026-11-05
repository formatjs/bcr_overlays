#include <cstdio>
#include <string>
#include <vector>

#include "GLES3/gl31.h"
#include "GLSLANG/ShaderLang.h"
#include "spirv-tools/libspirv.hpp"
#include "spirv-tools/optimizer.hpp"
#include "src/tint/api/tint.h"
#include "src/tint/lang/glsl/writer/writer.h"
#include "src/tint/lang/hlsl/writer/writer.h"
#include "src/tint/lang/msl/writer/writer.h"
#include "src/tint/lang/spirv/writer/writer.h"
#include "src/tint/lang/wgsl/reader/reader.h"
#include "src/tint/lang/wgsl/writer/writer.h"

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

#define CHECK_TINT(value)                             \
  do {                                                \
    if ((value) != tint::Success) {                   \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, \
                   (value).Failure().reason.c_str()); \
      return 1;                                       \
    }                                                 \
  } while (false)

constexpr char kShader[] = R"(
struct Buffer { values: array<u32, 4>, }
@group(0) @binding(0) var<storage, read_write> result: Buffer;
@compute @workgroup_size(4)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
  result.values[id.x] = id.x * 3u + 7u;
}
)";

int CheckGlsl(const std::string& source) {
  CHECK_CASE(sh::Initialize());
  ShBuiltInResources resources;
  sh::InitBuiltInResources(&resources);
  resources.MaxComputeWorkGroupSize = {128, 128, 64};
  resources.MaxShaderStorageBufferBindings = 4;
  ShHandle compiler = sh::ConstructCompiler(GL_COMPUTE_SHADER, SH_GLES3_1_SPEC,
                                            SH_ESSL_OUTPUT, &resources);
  CHECK_CASE(compiler);
  ShCompileOptions options;
  options.objectCode = true;
  const char* text = source.c_str();
  const bool compiled = sh::Compile(compiler, &text, 1, options);
  if (!compiled) {
    std::fprintf(stderr, "%s\n", sh::GetInfoLog(compiler).c_str());
  }
  sh::Destruct(compiler);
  CHECK_CASE(sh::Finalize());
  CHECK_CASE(compiled);
  return 0;
}

int CheckShaders() {
  tint::Source::File file("compute.wgsl", kShader);
  auto program = tint::wgsl::reader::Parse(&file);
  CHECK_CASE(program.IsValid());
  auto wgsl = tint::wgsl::writer::Generate(program);
  CHECK_TINT(wgsl);
  tint::Source::File round_trip("round-trip.wgsl", wgsl->wgsl);
  CHECK_CASE(tint::wgsl::reader::Parse(&round_trip).IsValid());

  auto spirv_ir = tint::wgsl::reader::WgslToIR(&file);
  CHECK_TINT(spirv_ir);
  tint::spirv::writer::Options spirv_options;
  spirv_options.bindings.storage.emplace(tint::BindingPoint{0, 0},
                                         tint::BindingPoint{0, 0});
  auto spirv = tint::spirv::writer::Generate(spirv_ir.Get(), spirv_options);
  CHECK_TINT(spirv);
  CHECK_CASE(spirv->workgroup_info.x == 4 && spirv->workgroup_info.y == 1 &&
             spirv->workgroup_info.z == 1);

  spvtools::SpirvTools validator(SPV_ENV_VULKAN_1_1);
  std::string diagnostics;
  validator.SetMessageConsumer([&](spv_message_level_t, const char*,
                                   const spv_position_t&,
                                   const char* text) { diagnostics += text; });
  CHECK_CASE(validator.Validate(spirv->spirv));
  std::string assembly;
  CHECK_CASE(validator.Disassemble(spirv->spirv, &assembly));
  CHECK_CASE(assembly.find("OpEntryPoint GLCompute") != std::string::npos);
  CHECK_CASE(assembly.find("LocalSize 4 1 1") != std::string::npos);
  CHECK_CASE(assembly.find("Binding 0") != std::string::npos);
  CHECK_CASE(assembly.find("UMin") != std::string::npos);
  spvtools::Optimizer optimizer(SPV_ENV_VULKAN_1_1);
  optimizer.RegisterPerformancePasses();
  std::vector<uint32_t> optimized;
  CHECK_CASE(
      optimizer.Run(spirv->spirv.data(), spirv->spirv.size(), &optimized));
  CHECK_CASE(!optimized.empty() && validator.Validate(optimized));
  std::string optimized_assembly;
  CHECK_CASE(validator.Disassemble(optimized, &optimized_assembly));
  CHECK_CASE(optimized_assembly.find("UMin") != std::string::npos);

  auto corrupted = spirv->spirv;
  corrupted[0] = 0;
  CHECK_CASE(!validator.Validate(corrupted));
  CHECK_CASE(!diagnostics.empty());

  auto glsl_ir = tint::wgsl::reader::WgslToIR(&file);
  CHECK_TINT(glsl_ir);
  tint::glsl::writer::Options glsl_options;
  glsl_options.bindings.storage.emplace(tint::BindingPoint{0, 0},
                                        tint::glsl::writer::BindingInfo{0});
  auto glsl = tint::glsl::writer::Generate(glsl_ir.Get(), glsl_options);
  CHECK_TINT(glsl);
  CHECK_CASE(glsl->glsl.find("#version") != std::string::npos);
  CHECK_CASE(CheckGlsl(glsl->glsl) == 0);
  CHECK_CASE(glsl->glsl.find("local_size_x = 4") != std::string::npos);

  auto hlsl_ir = tint::wgsl::reader::WgslToIR(&file);
  CHECK_TINT(hlsl_ir);
  tint::hlsl::writer::Options hlsl_options;
  hlsl_options.bindings.storage.emplace(tint::BindingPoint{0, 0},
                                        tint::BindingPoint{0, 0});
  auto hlsl = tint::hlsl::writer::Generate(hlsl_ir.Get(), hlsl_options);
  CHECK_TINT(hlsl);
  CHECK_CASE(hlsl->hlsl.find("numthreads(4, 1, 1)") != std::string::npos);
  CHECK_CASE(hlsl->hlsl.find("RWByteAddressBuffer") != std::string::npos);

  auto msl_ir = tint::wgsl::reader::WgslToIR(&file);
  CHECK_TINT(msl_ir);
  tint::msl::writer::Options msl_options;
  msl_options.bindings.storage.emplace(tint::BindingPoint{0, 0},
                                       tint::BindingPoint{0, 0});
  auto msl = tint::msl::writer::Generate(msl_ir.Get(), msl_options);
  CHECK_TINT(msl);
  CHECK_CASE(msl->msl.find("kernel void") != std::string::npos);
  CHECK_CASE(msl->msl.find("[[buffer(0)]]") != std::string::npos);

  tint::Source::File bad_syntax("syntax.wgsl", "fn broken(");
  CHECK_CASE(!tint::wgsl::reader::Parse(&bad_syntax).IsValid());
  tint::Source::File bad_type("type.wgsl", R"(
    @compute @workgroup_size(1) fn main() { let value: i32 = true; }
  )");
  CHECK_CASE(!tint::wgsl::reader::Parse(&bad_type).IsValid());
  CHECK_CASE(tint::wgsl::reader::WgslToIR(&bad_type) != tint::Success);
  return 0;
}

int main() {
  tint::Initialize();
  const int result = CheckShaders();
  tint::Shutdown();
  return result;
}
