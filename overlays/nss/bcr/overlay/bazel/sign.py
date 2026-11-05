"""Run original shlibsign without interpreting Bazel input symlinks as releases."""
from pathlib import Path
import subprocess
import sys

tool, source, output = map(Path, sys.argv[1:])
subprocess.run([str(tool.absolute()), '-i', str(source.resolve()),
                '-o', str(output.absolute())], check=True)
