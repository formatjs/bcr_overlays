#include <sys/socket.h>
#include <cstdio>

#include "wayland-client.h"
#include "wayland-server.h"

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

void Done(void* data, wl_callback* callback, uint32_t) {
  ++*static_cast<int*>(data);
  wl_callback_destroy(callback);
}

int main() {
  wl_display* server = wl_display_create();
  CHECK_CASE(server);
  int sockets[2];
  CHECK_CASE(socketpair(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0, sockets) == 0);
  wl_client* peer = wl_client_create(server, sockets[0]);
  CHECK_CASE(peer);
  wl_display* client = wl_display_connect_to_fd(sockets[1]);
  CHECK_CASE(client);
  int completed = 0;
  const wl_callback_listener listener{Done};
  wl_callback* callback = wl_display_sync(client);
  CHECK_CASE(callback &&
             wl_callback_add_listener(callback, &listener, &completed) == 0);
  CHECK_CASE(wl_display_flush(client) >= 0);
  CHECK_CASE(wl_event_loop_dispatch(wl_display_get_event_loop(server), 0) >= 0);
  wl_display_flush_clients(server);
  CHECK_CASE(wl_display_dispatch(client) >= 0);
  CHECK_CASE(completed == 1 && wl_display_get_error(client) == 0);
  wl_display_disconnect(client);
  wl_client_destroy(peer);
  wl_display_destroy(server);
  return 0;
}
