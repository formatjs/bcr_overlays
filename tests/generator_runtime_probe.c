#include <stdio.h>
#include <string.h>
#include <unistd.h>

extern const char *generator_expected_payload(void);

int main(int argc, char **argv) {
  char executable[4096];
  ssize_t length = readlink("/proc/self/exe", executable, sizeof(executable) - 1);
  if (argc != 2 || length < 0) return 1;
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
  FILE *output = fopen(argv[1], "w");
  if (!output) return 5;
  fputs(payload, output);
  return fclose(output) ? 6 : 0;
}
