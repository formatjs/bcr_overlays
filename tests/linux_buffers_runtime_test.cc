#include <dlfcn.h>
#include <drm_fourcc.h>
#include <gbm.h>

#include <array>
#include <cstdio>
#include <filesystem>
#include <string>

#include "base/at_exit.h"
#include "base/command_line.h"
#include "components/viz/common/resources/shared_image_format.h"
#include "ui/gfx/buffer_types.h"
#include "ui/gfx/linux/drm_util_linux.h"
#include "ui/gfx/linux/gbm_util.h"
#include "ui/gfx/linux/gbm_wrapper.h"
#include "ui/ozone/public/native_pixmap_usage_utils.h"

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
  struct Format {
    gfx::BufferFormat buffer;
    viz::SharedImageFormat image;
    uint32_t fourcc;
  };
  const std::array<Format, 4> formats = {{
      {gfx::BufferFormat::RGBA_8888, viz::SinglePlaneFormat::kRGBA_8888,
       DRM_FORMAT_ABGR8888},
      {gfx::BufferFormat::BGRA_8888, viz::SinglePlaneFormat::kBGRA_8888,
       DRM_FORMAT_ARGB8888},
      {gfx::BufferFormat::YUV_420_BIPLANAR, viz::MultiPlaneFormat::kNV12,
       DRM_FORMAT_NV12},
      {gfx::BufferFormat::P010, viz::MultiPlaneFormat::kP010, DRM_FORMAT_P010},
  }};
  for (const auto& format : formats) {
    CHECK_CASE(ui::GetFourCCFormatFromBufferFormat(format.buffer) ==
               format.fourcc);
    CHECK_CASE(ui::GetFourCCFormatFromSharedImageFormat(format.image) ==
               format.fourcc);
    CHECK_CASE(ui::GetBufferFormatFromFourCCFormat(format.fourcc) ==
               format.buffer);
    CHECK_CASE(ui::GetSharedImageFormatFromFourCCFormat(format.fourcc) ==
               format.image);
    CHECK_CASE(ui::IsValidBufferFormat(format.fourcc));
  }
  CHECK_CASE(!ui::IsValidBufferFormat(DRM_FORMAT_INVALID));
  CHECK_CASE(!ui::IsValidBufferFormat(0xffffffff));
  auto usage = ui::BufferUsageToNativePixmapUsage(
      gfx::BufferUsage::SCANOUT_CPU_READ_WRITE);
  CHECK_CASE(usage.Has(ui::NativePixmapUsage::kScanout));
  CHECK_CASE(usage.Has(ui::NativePixmapUsage::kCpuRead));
  CHECK_CASE(usage.Has(ui::NativePixmapUsage::kTexturing));
  const uint32_t expected_flags = GBM_BO_USE_LINEAR | GBM_BO_USE_SCANOUT;
  CHECK_CASE(ui::NativePixmapUsageToGbmFlags(usage) == expected_flags);
  CHECK_CASE(ui::BufferUsageToGbmFlags(
                 gfx::BufferUsage::SCANOUT_CPU_READ_WRITE) == expected_flags);
  CHECK_CASE(ui::BufferUsageToGbmFlags(gfx::BufferUsage::SCANOUT) ==
             (GBM_BO_USE_RENDERING | GBM_BO_USE_SCANOUT));
  void* library = dlopen("libgbm.so.1", RTLD_NOW | RTLD_NOLOAD);
  CHECK_CASE(library);
  void* create_device = dlsym(library, "gbm_create_device");
  CHECK_CASE(create_device);
  Dl_info info{};
  CHECK_CASE(dladdr(create_device, &info) && info.dli_fname);
  CHECK_CASE(std::filesystem::canonical(info.dli_fname)
                 .string()
                 .find("chromium_platform_headers") == std::string::npos);
  CHECK_CASE(!ui::CreateGbmDevice(-1));
  CHECK_CASE(dlclose(library) == 0);
  return 0;
}
