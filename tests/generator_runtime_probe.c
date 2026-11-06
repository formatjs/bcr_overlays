#include <stdio.h>
#include <string.h>
#include <unistd.h>

extern const char *generator_expected_payload(void);
extern const char *generator_relative_expected_payload(void);

int main(int argc, char **argv) {
  char executable[4096];
  ssize_t length = readlink("/proc/self/exe", executable, sizeof(executable) - 1);
  if (argc != 4 || length < 0) return 1;
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
  strcpy(name, "/icudtl.dat");
  FILE *host_icu = fopen(executable, "r");
  if (!host_icu || !fgets(snapshot, sizeof(snapshot), host_icu)) return 13;
  fclose(host_icu);
  if (strcmp(snapshot, "host ICU data\n") != 0) return 14;
  char argument_executable[4096];
  if (strlen(argv[0]) + sizeof("/icudtl.dat") >= sizeof(argument_executable)) return 17;
  strcpy(argument_executable, argv[0]);
  char *argument_name = strrchr(argument_executable, '/');
  if (!argument_name) return 18;
  strcpy(argument_name, "/icudtl.dat");
  FILE *argument_icu = fopen(argument_executable, "r");
  if (!argument_icu || !fgets(snapshot, sizeof(snapshot), argument_icu)) return 19;
  fclose(argument_icu);
  if (strcmp(snapshot, "host ICU data\n") != 0) return 20;
  FILE *target_icu = fopen(argv[3], "r");
  if (!target_icu || !fgets(snapshot, sizeof(snapshot), target_icu)) return 15;
  fclose(target_icu);
  if (strcmp(snapshot, "target ICU data\n") != 0) return 16;
  FILE *output = fopen(argv[1], "w");
  if (!output) return 5;
  fputs(payload, output);
  return fclose(output) ? 6 : 0;
}
