"""NSS ELF version-script transformation, matching upstream generate_mapfile."""
from pathlib import Path
import re
import sys

source, destination = map(Path, sys.argv[1:])
lines = []
for line in source.read_text().splitlines(keepends=True):
    if ';-' in line:
        continue
    line = line.replace(';+', '').replace(' DATA ', '').replace(';;', '')
    lines.append(re.sub(r';[^\n]*', ';', line))
destination.write_text(''.join(lines))
