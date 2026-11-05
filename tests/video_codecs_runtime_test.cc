#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

#include "aom/aom_decoder.h"
#include "aom/aom_encoder.h"
#include "aom/aomcx.h"
#include "aom/aomdx.h"
#include "vpx/vp8cx.h"
#include "vpx/vp8dx.h"
#include "vpx/vpx_decoder.h"
#include "vpx/vpx_encoder.h"

extern "C" {
#include "dav1d/dav1d.h"
unsigned dav1d_get_cpu_flags_x86(void);
extern unsigned dav1d_cpu_flags;
}

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

constexpr unsigned kSize = 32;
unsigned Pixel(unsigned plane, unsigned x, unsigned y, bool high, bool flat) {
  return flat ? 96 + plane * 24
              : (x * 13 + y * 7 + plane * 173) % (high ? 1024 : 256);
}

template <typename Image>
void Fill(Image& image, bool high, bool flat) {
  for (unsigned plane = 0; plane < 3; ++plane) {
    const unsigned size = plane ? kSize / 2 : kSize;
    for (unsigned y = 0; y < size; ++y) {
      uint8_t* row = image.planes[plane] + y * image.stride[plane];
      for (unsigned x = 0; x < size; ++x) {
        if (high)
          reinterpret_cast<uint16_t*>(row)[x] = Pixel(plane, x, y, high, flat);
        else
          row[x] = Pixel(plane, x, y, high, flat);
      }
    }
  }
}

template <typename Image>
int CheckPixels(const Image& image, bool high, bool flat, bool storage_high) {
  CHECK_CASE(image.d_w == kSize && image.d_h == kSize);
  for (unsigned plane = 0; plane < 3; ++plane) {
    const unsigned size = plane ? kSize / 2 : kSize;
    for (unsigned y = 0; y < size; ++y) {
      const uint8_t* row = image.planes[plane] + y * image.stride[plane];
      for (unsigned x = 0; x < size; ++x) {
        const unsigned value =
            storage_high ? reinterpret_cast<const uint16_t*>(row)[x] : row[x];
        const int difference =
            static_cast<int>(value) - Pixel(plane, x, y, high, flat);
        CHECK_CASE(std::abs(difference) <= (flat ? 2 : 0));
      }
    }
  }
  return 0;
}

int CheckVpx(bool vp9, bool high) {
  vpx_codec_iface_t* encoder_interface =
      vp9 ? vpx_codec_vp9_cx() : vpx_codec_vp8_cx();
  vpx_codec_iface_t* decoder_interface =
      vp9 ? vpx_codec_vp9_dx() : vpx_codec_vp8_dx();
  if (high) {
    CHECK_CASE(vpx_codec_get_caps(encoder_interface) &
               VPX_CODEC_CAP_HIGHBITDEPTH);
    CHECK_CASE(vpx_codec_get_caps(decoder_interface) &
               VPX_CODEC_CAP_HIGHBITDEPTH);
  }
  vpx_codec_enc_cfg_t config{};
  CHECK_CASE(vpx_codec_enc_config_default(encoder_interface, &config, 0) ==
             VPX_CODEC_OK);
  config.g_w = config.g_h = kSize;
  config.g_threads = 2;
  config.g_lag_in_frames = 0;
  config.g_timebase = {1, 30};
  config.rc_target_bitrate = 256;
  config.g_profile = high ? 2 : 0;
  config.g_bit_depth = high ? VPX_BITS_10 : VPX_BITS_8;
  config.g_input_bit_depth = high ? 10 : 8;
  vpx_codec_ctx_t encoder{}, decoder{};
  CHECK_CASE(vpx_codec_enc_init(&encoder, encoder_interface, &config,
                                high ? VPX_CODEC_USE_HIGHBITDEPTH : 0) ==
             VPX_CODEC_OK);
  CHECK_CASE(vpx_codec_control(&encoder, VP8E_SET_CPUUSED, 8) == VPX_CODEC_OK);
  if (vp9)
    CHECK_CASE(vpx_codec_control(&encoder, VP9E_SET_LOSSLESS, 1) ==
               VPX_CODEC_OK);
  vpx_image_t image{};
  CHECK_CASE(vpx_img_alloc(&image, high ? VPX_IMG_FMT_I42016 : VPX_IMG_FMT_I420,
                           kSize, kSize, 32));
  Fill(image, high, !vp9);
  CHECK_CASE(vpx_codec_encode(&encoder, &image, 0, 1, 0, VPX_DL_REALTIME) ==
             VPX_CODEC_OK);
  std::vector<uint8_t> bytes;
  vpx_codec_iter_t iterator = nullptr;
  const vpx_codec_cx_pkt_t* packet;
  while ((packet = vpx_codec_get_cx_data(&encoder, &iterator))) {
    if (packet->kind == VPX_CODEC_CX_FRAME_PKT) {
      const auto* data = static_cast<const uint8_t*>(packet->data.frame.buf);
      bytes.insert(bytes.end(), data, data + packet->data.frame.sz);
    }
  }
  CHECK_CASE(!bytes.empty());
  vpx_codec_dec_cfg_t decoder_config{};
  decoder_config.threads = 2;
  CHECK_CASE(vpx_codec_dec_init(&decoder, decoder_interface, &decoder_config,
                                0) == VPX_CODEC_OK);
  CHECK_CASE(vpx_codec_decode(&decoder, bytes.data(), bytes.size(), nullptr,
                              0) == VPX_CODEC_OK);
  iterator = nullptr;
  const vpx_image_t* decoded = vpx_codec_get_frame(&decoder, &iterator);
  CHECK_CASE(decoded != nullptr);
  CHECK_CASE(decoded->bit_depth == (high ? 10u : 8u));
  CHECK_CASE(CheckPixels(*decoded, high, !vp9,
                         decoded->fmt & VPX_IMG_FMT_HIGHBITDEPTH) == 0);
  CHECK_CASE(vpx_codec_get_frame(&decoder, &iterator) == nullptr);
  vpx_img_free(&image);
  CHECK_CASE(vpx_codec_destroy(&decoder) == VPX_CODEC_OK);
  CHECK_CASE(vpx_codec_destroy(&encoder) == VPX_CODEC_OK);
  return 0;
}

int CheckDav1d(const std::vector<uint8_t>& bytes, bool high) {
  Dav1dSettings settings;
  dav1d_default_settings(&settings);
  settings.n_threads = 2;
  settings.max_frame_delay = 1;
  Dav1dContext* context = nullptr;
  CHECK_CASE(dav1d_open(&context, &settings) == 0);
  CHECK_CASE(context != nullptr);
  CHECK_CASE(dav1d_get_cpu_flags_x86() != 0);
  CHECK_CASE(dav1d_cpu_flags != 0);
  Dav1dData input{};
  uint8_t* storage = dav1d_data_create(&input, bytes.size());
  CHECK_CASE(storage != nullptr);
  std::memcpy(storage, bytes.data(), bytes.size());
  CHECK_CASE(dav1d_send_data(context, &input) == 0);
  Dav1dPicture picture{};
  CHECK_CASE(dav1d_get_picture(context, &picture) == 0);
  CHECK_CASE(picture.p.bpc == (high ? 10 : 8));
  CHECK_CASE(picture.p.layout == DAV1D_PIXEL_LAYOUT_I420);
  struct View {
    unsigned d_w, d_h;
    const uint8_t* planes[3];
    ptrdiff_t stride[3];
  } view{static_cast<unsigned>(picture.p.w),
         static_cast<unsigned>(picture.p.h),
         {static_cast<const uint8_t*>(picture.data[0]),
          static_cast<const uint8_t*>(picture.data[1]),
          static_cast<const uint8_t*>(picture.data[2])},
         {picture.stride[0], picture.stride[1], picture.stride[1]}};
  CHECK_CASE(CheckPixels(view, high, false, high) == 0);
  dav1d_picture_unref(&picture);
  CHECK_CASE(dav1d_get_picture(context, &picture) == DAV1D_ERR(EAGAIN));
  dav1d_data_unref(&input);
  Dav1dData invalid{};
  storage = dav1d_data_create(&invalid, 1);
  CHECK_CASE(storage != nullptr);
  storage[0] = 0xff;
  int result = dav1d_send_data(context, &invalid);
  if (result == 0)
    result = dav1d_get_picture(context, &picture);
  CHECK_CASE(result == DAV1D_ERR(EINVAL));
  dav1d_data_unref(&invalid);
  dav1d_close(&context);
  return 0;
}

int CheckAv1(bool high) {
  aom_codec_enc_cfg_t config{};
  CHECK_CASE(aom_codec_enc_config_default(aom_codec_av1_cx(), &config,
                                          AOM_USAGE_REALTIME) == AOM_CODEC_OK);
  config.g_w = config.g_h = kSize;
  config.g_threads = 2;
  config.g_lag_in_frames = 0;
  config.g_timebase = {1, 30};
  config.rc_target_bitrate = 256;
  config.g_bit_depth = high ? AOM_BITS_10 : AOM_BITS_8;
  config.g_input_bit_depth = high ? 10 : 8;
  aom_codec_ctx_t encoder{}, decoder{};
  CHECK_CASE(aom_codec_enc_init(&encoder, aom_codec_av1_cx(), &config,
                                high ? AOM_CODEC_USE_HIGHBITDEPTH : 0) ==
             AOM_CODEC_OK);
  CHECK_CASE(aom_codec_control(&encoder, AOME_SET_CPUUSED, 8) == AOM_CODEC_OK);
  CHECK_CASE(aom_codec_control(&encoder, AV1E_SET_LOSSLESS, 1) == AOM_CODEC_OK);
  aom_image_t image{};
  CHECK_CASE(aom_img_alloc(&image, high ? AOM_IMG_FMT_I42016 : AOM_IMG_FMT_I420,
                           kSize, kSize, 32));
  Fill(image, high, false);
  CHECK_CASE(aom_codec_encode(&encoder, &image, 0, 1, 0) == AOM_CODEC_OK);
  std::vector<uint8_t> bytes;
  aom_codec_iter_t iterator = nullptr;
  const aom_codec_cx_pkt_t* packet;
  while ((packet = aom_codec_get_cx_data(&encoder, &iterator))) {
    if (packet->kind == AOM_CODEC_CX_FRAME_PKT) {
      const auto* data = static_cast<const uint8_t*>(packet->data.frame.buf);
      bytes.insert(bytes.end(), data, data + packet->data.frame.sz);
    }
  }
  CHECK_CASE(!bytes.empty());
  CHECK_CASE(CheckDav1d(bytes, high) == 0);
  aom_codec_dec_cfg_t decoder_config{};
  decoder_config.threads = 2;
  CHECK_CASE(aom_codec_dec_init(&decoder, aom_codec_av1_dx(), &decoder_config,
                                0) == AOM_CODEC_OK);
  CHECK_CASE(aom_codec_decode(&decoder, bytes.data(), bytes.size(), nullptr) ==
             AOM_CODEC_OK);
  iterator = nullptr;
  const aom_image_t* decoded = aom_codec_get_frame(&decoder, &iterator);
  CHECK_CASE(decoded != nullptr);
  CHECK_CASE(decoded->bit_depth == (high ? 10u : 8u));
  CHECK_CASE(CheckPixels(*decoded, high, false,
                         decoded->fmt & AOM_IMG_FMT_HIGHBITDEPTH) == 0);
  CHECK_CASE(aom_codec_get_frame(&decoder, &iterator) == nullptr);
  aom_img_free(&image);
  CHECK_CASE(aom_codec_destroy(&decoder) == AOM_CODEC_OK);
  CHECK_CASE(aom_codec_destroy(&encoder) == AOM_CODEC_OK);
  return 0;
}

int main() {
  CHECK_CASE(CheckVpx(false, false) == 0);
  CHECK_CASE(CheckVpx(true, false) == 0);
  CHECK_CASE(CheckVpx(true, true) == 0);
  CHECK_CASE(CheckAv1(false) == 0);
  CHECK_CASE(CheckAv1(true) == 0);
  std::puts(
      "VP8, VP9, AV1 and dav1d SIMD passed; VP9/AV1 8/10-bit lossless pixels "
      "exact");
  return 0;
}
