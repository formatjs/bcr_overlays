#include <algorithm>
#include <cstring>
#include <memory>
#include <optional>

#include "base/at_exit.h"
#include "base/command_line.h"
#include "base/functional/bind.h"
#include "base/run_loop.h"
#include "base/task/single_thread_task_executor.h"
#include "base/timer/timer.h"
#include "net/base/address_list.h"
#include "net/base/io_buffer.h"
#include "net/base/ip_endpoint.h"
#include "net/base/net_errors.h"
#include "net/log/net_log_source.h"
#include "net/socket/tcp_client_socket.h"
#include "net/socket/tcp_server_socket.h"
#include "net/traffic_annotation/network_traffic_annotation.h"
#include "url/gurl.h"

class Completion {
 public:
  net::CompletionOnceCallback callback() {
    return base::BindOnce(&Completion::Finish, base::Unretained(this));
  }
  int Wait(int result) {
    if (result != net::ERR_IO_PENDING) return result;
    if (result_ != net::ERR_IO_PENDING) return result_;
    base::OneShotTimer timeout;
    timeout.Start(FROM_HERE, base::Seconds(10),
                  base::BindOnce(&Completion::Finish, base::Unretained(this),
                                 net::ERR_TIMED_OUT));
    loop_.Run();
    return result_;
  }

 private:
  void Finish(int result) {
    result_ = result;
    loop_.Quit();
  }
  base::RunLoop loop_;
  int result_ = net::ERR_IO_PENDING;
};

bool Transfer(net::StreamSocket* socket, net::IOBuffer* buffer, int size,
              bool writing) {
  auto remaining = base::MakeRefCounted<net::DrainableIOBuffer>(buffer, size);
  constexpr auto annotation = net::DefineNetworkTrafficAnnotation(
      "chromium_cross_compile_smoke", R"(
        semantics { sender: "CI smoke" description: "Loopback socket test."
          trigger: "CI" data: "Fixed test payload." destination: LOCAL }
        policy { cookies_allowed: NO setting: "CI only."
          policy_exception_justification: "Not user-facing." })");
  while (remaining->BytesRemaining()) {
    Completion completion;
    int result = writing
        ? socket->Write(remaining.get(), remaining->BytesRemaining(),
                         completion.callback(), annotation)
        : socket->Read(remaining.get(), remaining->BytesRemaining(),
                        completion.callback());
    result = completion.Wait(result);
    if (result <= 0 || result > remaining->BytesRemaining()) return false;
    remaining->DidConsume(result);
  }
  return true;
}

int main(int argc, char** argv) {
  base::AtExitManager at_exit;
  base::CommandLine::Init(argc, argv);
  base::SingleThreadTaskExecutor executor(base::MessagePumpType::IO);
  GURL url("https://EXAMPLE.com:443/a/../b?x=1");
  if (!url.is_valid() || url.spec() != "https://example.com/b?x=1") return 10;

  net::TCPServerSocket listener(nullptr, net::NetLogSource());
  if (listener.Listen(net::IPEndPoint(net::IPAddress::IPv4Localhost(), 0), 1,
                       std::nullopt) != net::OK) return 11;
  net::IPEndPoint endpoint;
  if (listener.GetLocalAddress(&endpoint) != net::OK) return 12;
  Completion accepting;
  std::unique_ptr<net::StreamSocket> accepted;
  int accept_result = listener.Accept(&accepted, accepting.callback());
  net::TCPClientSocket client(net::AddressList(endpoint), nullptr, nullptr,
                              nullptr, net::NetLogSource());
  Completion connecting;
  if (connecting.Wait(client.Connect(connecting.callback())) != net::OK ||
      accepting.Wait(accept_result) != net::OK) return 13;

  constexpr char payload[] = "Chromium loopback \xc3\xa9";
  auto sent = base::MakeRefCounted<net::IOBufferWithSize>(sizeof(payload));
  auto received = base::MakeRefCounted<net::IOBufferWithSize>(sizeof(payload));
  std::memcpy(sent->data(), payload, sizeof(payload));
  if (!Transfer(&client, sent.get(), sizeof(payload), true) ||
      !Transfer(accepted.get(), received.get(), sizeof(payload), false) ||
      std::memcmp(received->data(), payload, sizeof(payload)) != 0) return 14;
  std::fill_n(sent->data(), sizeof(payload), 0);
  if (!Transfer(accepted.get(), received.get(), sizeof(payload), true) ||
      !Transfer(&client, sent.get(), sizeof(payload), false) ||
      std::memcmp(sent->data(), payload, sizeof(payload)) != 0) return 15;
  return 0;
}
