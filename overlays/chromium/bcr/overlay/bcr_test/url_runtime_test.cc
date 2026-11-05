#include <cstdio>
#include <cstdlib>
#include <memory>
#include <string>

#include "base/at_exit.h"
#include "base/files/file.h"
#include "base/files/memory_mapped_file.h"
#include "base/i18n/icu_util.h"
#include "mojo/core/embedder/embedder.h"
#include "partition_alloc/partition_alloc.h"
#include "rules_cc/cc/runfiles/runfiles.h"
#include "url/gurl.h"
#include "url/mojom/origin.mojom.h"
#include "url/mojom/scheme_host_port.mojom.h"
#include "url/mojom/url.mojom.h"
#include "url/origin.h"
#include "url/scheme_host_port.h"

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

int main(int argc, char** argv) {
  partition_alloc::PartitionAllocGlobalInit([](size_t) { std::abort(); });
  base::AtExitManager at_exit;
  CHECK_CASE(argc == 2);
  std::string error;
  std::unique_ptr<rules_cc::cc::runfiles::Runfiles> runfiles(
      rules_cc::cc::runfiles::Runfiles::CreateForTest(&error));
  CHECK_CASE(runfiles);
  base::File data(base::FilePath(runfiles->Rlocation(argv[1])),
                  base::File::FLAG_OPEN | base::File::FLAG_READ);
  CHECK_CASE(data.IsValid());
  CHECK_CASE(base::i18n::InitializeICUWithFileDescriptor(
      data.TakePlatformFile(), base::MemoryMappedFile::Region::kWholeFile));
  mojo::core::Init();

  GURL canonical("HTTP://User:pass@ExAmPlE.COM:80/a/../b?q=x#Frag");
  CHECK_CASE(canonical.is_valid());
  CHECK_CASE(canonical.spec() == "http://User:pass@example.com/b?q=x#Frag");
  GURL idna(u"https://b\u00fccher.example/a");
  CHECK_CASE(idna.is_valid() && idna.host() == "xn--bcher-kva.example");
  CHECK_CASE(GURL("http://0x7f000001/").host() == "127.0.0.1");
  CHECK_CASE(!GURL("http://[broken/").is_valid());
  CHECK_CASE(!GURL("https://example.com:65536/").is_valid());

  auto encoded_url = url::mojom::Url::Serialize(&canonical);
  GURL decoded_url;
  CHECK_CASE(url::mojom::Url::Deserialize(encoded_url, &decoded_url));
  CHECK_CASE(decoded_url == canonical);
  auto malformed_url = url::mojom::Url::New("http://[");
  auto malformed_bytes = url::mojom::Url::Serialize(&malformed_url);
  CHECK_CASE(!url::mojom::Url::Deserialize(malformed_bytes, &decoded_url));
  CHECK_CASE(
      !url::mojom::Url::Deserialize(encoded_url.data(), 4, &decoded_url));
  GURL invalid_url("http://[");
  auto empty_url = url::mojom::Url::Serialize(&invalid_url);
  CHECK_CASE(url::mojom::Url::Deserialize(empty_url, &decoded_url));
  CHECK_CASE(decoded_url.is_empty());

  auto origin = url::Origin::Create(canonical);
  CHECK_CASE(origin.Serialize() == "http://example.com");
  CHECK_CASE(origin.IsSameOriginWith(GURL("http://example.com:80/other")));
  CHECK_CASE(!origin.IsSameOriginWith(GURL("https://example.com/")));
  auto encoded_origin = url::mojom::Origin::Serialize(&origin);
  url::Origin decoded_origin;
  CHECK_CASE(url::mojom::Origin::Deserialize(encoded_origin, &decoded_origin));
  CHECK_CASE(origin.IsSameOriginWith(decoded_origin));
  auto opaque = origin.DeriveNewOpaqueOrigin();
  auto encoded_opaque = url::mojom::Origin::Serialize(&opaque);
  CHECK_CASE(url::mojom::Origin::Deserialize(encoded_opaque, &decoded_origin));
  CHECK_CASE(decoded_origin.opaque());
  CHECK_CASE(opaque.IsSameOriginWith(decoded_origin));
  CHECK_CASE(!opaque.IsSameOriginWith(origin.DeriveNewOpaqueOrigin()));
  auto malformed_origin =
      url::mojom::Origin::New("https", "ExAmPlE.com", 443, std::nullopt);
  auto malformed_origin_bytes =
      url::mojom::Origin::Serialize(&malformed_origin);
  CHECK_CASE(!url::mojom::Origin::Deserialize(malformed_origin_bytes,
                                              &decoded_origin));

  url::SchemeHostPort tuple(idna);
  auto encoded_tuple = url::mojom::SchemeHostPort::Serialize(&tuple);
  url::SchemeHostPort decoded_tuple;
  CHECK_CASE(
      url::mojom::SchemeHostPort::Deserialize(encoded_tuple, &decoded_tuple));
  CHECK_CASE(decoded_tuple == tuple);
  url::SchemeHostPort empty_tuple;
  auto encoded_empty = url::mojom::SchemeHostPort::Serialize(&empty_tuple);
  CHECK_CASE(
      url::mojom::SchemeHostPort::Deserialize(encoded_empty, &decoded_tuple));
  CHECK_CASE(decoded_tuple == empty_tuple);
  auto malformed_tuple =
      url::mojom::SchemeHostPort::New("https", "bad/host", 443);
  auto malformed_tuple_bytes =
      url::mojom::SchemeHostPort::Serialize(&malformed_tuple);
  CHECK_CASE(!url::mojom::SchemeHostPort::Deserialize(malformed_tuple_bytes,
                                                      &decoded_tuple));
  return 0;
}
