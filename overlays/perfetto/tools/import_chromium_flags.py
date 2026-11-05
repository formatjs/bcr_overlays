#!/usr/bin/env python3
"""Import Chromium's pinned Perfetto runtime build flags."""
import gzip
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
graph = json.loads(gzip.decompress(Path(sys.argv[1]).read_bytes()))
flags = graph['targets']['//third_party/perfetto/gn:gen_buildflags']['response_file_contents']
if flags[0] != '--flags' or 'PERFETTO_CHROMIUM_BUILD=true' not in flags:
    raise ValueError('expected Chromium runtime flags')
(root / 'bcr/overlay/bazel/chromium_flags.bzl').write_text(
    '"""Generated from Chromium 142 native graph; tools/import_chromium_flags.py."""\n\n'
    + 'CHROMIUM_FLAGS = ' + json.dumps(flags[1:], indent=4) + '\n')
