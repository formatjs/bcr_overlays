#include <unistd.h>

#include <cstdio>
#include <string>
#include <vector>

#include "base/at_exit.h"
#include "base/command_line.h"
#include "base/task/single_thread_task_executor.h"
#include "ui/gfx/linux/gbm_buffer.h"
#include "ui/gfx/linux/gpu_memory_buffer_support_x11.h"
#include "ui/gfx/x/connection.h"
#include "ui/gfx/x/dri3.h"
#include "ui/gfx/x/event.h"
#include "ui/gfx/x/future.h"
#include "ui/gfx/x/xproto.h"

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

int CheckX11Extensions(const std::string& display);

int main(int argc, char** argv) {
  base::AtExitManager at_exit;
  base::CommandLine::Init(argc, argv);
  base::SingleThreadTaskExecutor executor;
  alarm(30);
  const std::string display =
      base::CommandLine::ForCurrentProcess()->GetSwitchValueASCII(
          "x11-display");
  CHECK_CASE(!display.empty());
  base::CommandLine::ForCurrentProcess()->AppendSwitchASCII("display", display);
  x11::Connection connection(display);
  CHECK_CASE(connection.Ready());
  auto key = connection.KeysymToKeycode('a');
  CHECK_CASE(static_cast<uint32_t>(key) != 0);
  CHECK_CASE(connection.KeycodeToKeysym(key, 0) == 'a');
  CHECK_CASE(connection.KeycodeToKeysym(key, 1) == 'A');
  CHECK_CASE(connection.default_screen().width_in_pixels >= 64);
  CHECK_CASE(connection.default_screen().height_in_pixels >= 48);
  auto window = connection.GenerateId<x11::Window>();
  auto created = connection
                     .CreateWindow({
                         .depth = connection.default_root_depth().depth,
                         .wid = window,
                         .parent = connection.default_screen().root,
                         .width = 64,
                         .height = 48,
                         .override_redirect = x11::Bool32(true),
                         .event_mask = x11::EventMask::PropertyChange,
                     })
                     .Sync();
  CHECK_CASE(!created.error);
  auto attributes = connection.GetWindowAttributes({window}).Sync();
  CHECK_CASE(attributes && attributes->map_state == x11::MapState::Unmapped);
  CHECK_CASE(attributes->override_redirect);
  CHECK_CASE(!connection.MapWindow(window).Sync().error);
  attributes = connection.GetWindowAttributes({window}).Sync();
  CHECK_CASE(attributes && attributes->map_state == x11::MapState::Viewable);
  auto geometry = connection.GetGeometry(window).Sync();
  CHECK_CASE(geometry && geometry->width == 64 && geometry->height == 48);
  auto atom = connection.GetAtom("_NET_WM_NAME");
  CHECK_CASE(atom != x11::Atom::None);
  const std::vector<uint8_t> bytes = {'b', 'a', 'z', 'e', 'l',
                                      0,   'X', '1', '1'};
  CHECK_CASE(
      !connection.SetArrayProperty(window, atom, x11::Atom::STRING, bytes)
           .Sync()
           .error);
  std::vector<uint8_t> returned;
  x11::Atom type;
  CHECK_CASE(connection.GetArrayProperty(window, atom, &returned, &type));
  CHECK_CASE(type == x11::Atom::STRING && returned == bytes);
  connection.ReadResponses();
  bool property_event = false;
  for (const auto& event : connection.events()) {
    const auto* property = event.As<x11::PropertyNotifyEvent>();
    if (property && property->window == window && property->atom == atom &&
        property->state == x11::Property::NewValue) {
      property_event = true;
    }
  }
  CHECK_CASE(property_event);
  std::vector<uint8_t> large(1 << 20);
  for (size_t i = 0; i < large.size(); ++i)
    large[i] = static_cast<uint8_t>(i * 37 + 11);
  auto large_atom = x11::Atom::WM_COMMAND;
  CHECK_CASE(
      !connection.SetArrayProperty(window, large_atom, x11::Atom::STRING, large)
           .Sync()
           .error);
  CHECK_CASE(connection.GetArrayProperty(window, large_atom, &returned));
  CHECK_CASE(returned == large);
  auto missing = connection.GenerateId<x11::Window>();
  auto invalid = connection.GetGeometry(missing).Sync();
  CHECK_CASE(!invalid && invalid.error);
  auto* drawable_error = static_cast<x11::DrawableError*>(invalid.error.get());
  CHECK_CASE(drawable_error->bad_value == static_cast<uint32_t>(missing));
  CHECK_CASE(!connection.DestroyWindow(window).Sync().error);
  CHECK_CASE(!connection.GetWindowAttributes({window}).Sync());
  CHECK_CASE(!connection.dri3().present());
  CHECK_CASE(x11::Connection::Get()->Ready());
  auto* gpu_buffers = ui::GpuMemoryBufferSupportX11::GetInstance();
  CHECK_CASE(!gpu_buffers->has_gbm_device());
  CHECK_CASE(gpu_buffers->supported_configs().empty());
  CHECK_CASE(!gpu_buffers->CanCreateNativePixmapForFormat(
      gfx::BufferFormat::RGBA_8888));
  CHECK_CASE(!gpu_buffers->CreateBuffer(gfx::BufferFormat::RGBA_8888,
                                        gfx::Size(16, 16),
                                        gfx::BufferUsage::GPU_READ));
  x11::Connection absent(":65534");
  CHECK_CASE(!absent.Ready());
  CHECK_CASE(CheckX11Extensions(display) == 0);
  std::puts(
      "X11 window, property/event, 1 MiB transfer, error replies and "
      "absent-DRI3 buffer rejection verified");
  return 0;
}
