"""Run GRIT with relocatable UTF-8 Windows resource outputs."""

import argparse
import os
from pathlib import Path
import subprocess
import sys


def normalize_resource(path, root, build):
    data = path.read_bytes()
    encoding = 'utf-16' if data.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'
    text = data.decode(encoding)
    text = text.replace(str(root) + os.sep, os.path.relpath(root, build) + '/')
    path.write_text(text, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resource-output', action='append', required=True, type=Path)
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    arguments = args.arguments[1:] if args.arguments[:1] == ['--'] else args.arguments
    script = Path(__file__).resolve()
    subprocess.run([sys.executable, str(script.with_name('grit.py')), *arguments], check=True)
    for path in args.resource_output:
        normalize_resource(path, script.parents[2], Path.cwd())


if __name__ == '__main__':
    main()
