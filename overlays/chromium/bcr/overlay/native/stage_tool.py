# SPDX-License-Identifier: MIT
"""Materialize native tool runtimes independently of generator working trees."""
import json
from pathlib import Path
import shutil
import sys

for source, output in json.loads(Path(sys.argv[1]).read_text()):
    source = Path(source)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, output)
    output.chmod(0o755 if source.stat().st_mode & 0o111 else 0o644)
