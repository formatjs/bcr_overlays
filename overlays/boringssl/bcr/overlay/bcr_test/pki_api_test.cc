#include <string>

#include "pki/pem.h"

int main() {
  const std::string pem =
      "-----BEGIN CERTIFICATE-----\nTQ==\n-----END CERTIFICATE-----\n";
  auto decoded = bssl::PEMDecodeSingle(pem, "CERTIFICATE");
  if (!decoded || *decoded != "M")
    return 1;
  if (bssl::PEMDecodeSingle(pem, "PRIVATE KEY"))
    return 2;
  if (bssl::PEMDecodeSingle(pem + pem, "CERTIFICATE"))
    return 3;
  if (bssl::PEMDecodeSingle(
          "-----BEGIN CERTIFICATE-----\n!\n-----END CERTIFICATE-----\n",
          "CERTIFICATE"))
    return 4;
  return 0;
}
