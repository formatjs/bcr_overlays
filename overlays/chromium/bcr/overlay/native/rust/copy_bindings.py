"""Stage one generated binding in the directory expected by Chromium's wrapper."""
from pathlib import Path
import shutil
import sys

output = Path(sys.argv[2])
output.mkdir(parents=True, exist_ok=True)
shutil.copyfile(sys.argv[1], output / (sys.argv[3] if len(sys.argv) > 3 else 'bindings.rs'))
