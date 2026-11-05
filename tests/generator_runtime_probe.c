#include <stdio.h>
#include <string.h>
#include <unistd.h>

extern const char *generator_expected_payload(void);
extern const char *generator_relative_expected_payload(void);

int main(int argc, char **argv) {
  char executable[4096];
  ssize_t length = readlink("/proc/self/exe", executable, sizeof(executable) - 1);
  if (argc != 3 || length < 0) return 1;
  executable[length] = '\0';
  char *name = strrchr(executable, '/');
  if (!name || (size_t)(name - executable) + sizeof("/payload.txt") > sizeof(executable)) return 2;
  strcpy(name, "/payload.txt");
  FILE *input = fopen(executable, "r");
  if (!input) {
    fputs("missing declared runtime data\n", stderr);
    return 3;
  }
  char payload[128];
  if (!fgets(payload, sizeof(payload), input)) return 4;
  fclose(input);
  if (strcmp(payload, generator_expected_payload()) != 0) return 7;
  if (strcmp(payload, generator_relative_expected_payload()) != 0) return 8;
  strcpy(name, "/snapshot_blob.bin");
  FILE *host = fopen(executable, "r");
  char snapshot[128];
  if (!host || !fgets(snapshot, sizeof(snapshot), host)) return 9;
  fclose(host);
  if (strcmp(snapshot, "host snapshot\n") != 0) return 10;
  FILE *target = fopen(argv[2], "r");
  if (!target || !fgets(snapshot, sizeof(snapshot), target)) return 11;
  fclose(target);
  if (strcmp(snapshot, "target snapshot\n") != 0) return 12;
  FILE *output = fopen(argv[1], "w");
  if (!output) return 5;
  fputs(payload, output);
  return fclose(output) ? 6 : 0;
}
