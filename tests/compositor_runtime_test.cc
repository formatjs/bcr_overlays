#include <cstdio>
#include <optional>

#include "base/at_exit.h"
#include "cc/base/simple_enclosed_region.h"
#include "cc/layers/layer.h"
#include "cc/trees/occlusion.h"
#include "services/network/public/cpp/cors/cors.h"
#include "services/network/public/mojom/fetch_api.mojom-shared.h"
#include "ui/gfx/geometry/rect.h"
#include "ui/gfx/geometry/transform.h"
#include "url/gurl.h"
#include "url/origin.h"

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

int main() {
  base::AtExitManager at_exit;
  auto root = cc::Layer::Create();
  auto sibling = cc::Layer::Create();
  auto child = cc::Layer::Create();
  root->AddChild(child);
  root->AddChild(sibling);
  CHECK_CASE(root->children().size() == 2);
  sibling->AddChild(child);
  CHECK_CASE(root->children().size() == 1);
  CHECK_CASE(child->parent() == sibling.get());
  child->RemoveFromParent();
  CHECK_CASE(child->parent() == nullptr && sibling->children().empty());
  root->AddChild(child);
  sibling.reset();
  CHECK_CASE(root->children().size() == 2);
  root->RemoveAllChildren();
  CHECK_CASE(child->parent() == nullptr);

  gfx::Transform transform;
  transform.Translate(10, 20);
  transform.Scale(2, 2);
  cc::Occlusion occlusion(transform,
                          cc::SimpleEnclosedRegion(gfx::Rect(10, 20, 200, 200)),
                          cc::SimpleEnclosedRegion());
  CHECK_CASE(occlusion.IsOccluded(gfx::Rect(0, 0, 100, 100)));
  CHECK_CASE(!occlusion.IsOccluded(gfx::Rect(80, 0, 40, 100)));
  CHECK_CASE(occlusion.GetUnoccludedContentRect(gfx::Rect(80, 0, 40, 100)) ==
             gfx::Rect(100, 0, 20, 100));
  CHECK_CASE(!occlusion.IsOccluded(gfx::Rect(200, 200, 10, 10)));

  const GURL response("https://service.example/data");
  const auto origin = url::Origin::Create(GURL("https://page.example/"));
  using Credentials = network::mojom::CredentialsMode;
  CHECK_CASE(network::cors::CheckAccess(response, "*", std::nullopt,
                                        Credentials::kOmit, origin)
                 .has_value());
  CHECK_CASE(!network::cors::CheckAccess(response, "*", "true",
                                         Credentials::kInclude, origin)
                  .has_value());
  CHECK_CASE(network::cors::CheckAccess(response, origin.Serialize(), "true",
                                        Credentials::kInclude, origin)
                 .has_value());
  CHECK_CASE(!network::cors::CheckAccess(response, "https://other.example",
                                         "true", Credentials::kInclude, origin)
                  .has_value());
  CHECK_CASE(!network::cors::CheckAccess(response, origin.Serialize(),
                                         std::nullopt, Credentials::kInclude,
                                         origin)
                  .has_value());
  std::puts(
      "Compositor: layer ownership/reparenting, transformed occlusion; network "
      "CORS credential checks passed");
  return 0;
}
