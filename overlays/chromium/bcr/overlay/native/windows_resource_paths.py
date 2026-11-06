# SPDX-License-Identifier: MIT
"""Normalize RC filenames for LLVM's Linux-hosted resource compiler."""
from pathlib import Path
import re
import sys


FILES = re.compile(
    r'(?m)^(\s*\S+\s+(?:ICON|BITMAP|CURSOR|FONT|HTML|MESSAGETABLE|TYPELIB|RCDATA|DLGINCLUDE|\d+)\b[^"\r\n]*)'
    r'"([^"\r\n]+\.(?:ico|bmp|cur|manifest|bin|png|rc|dlg|tlb|h))"', re.I)


def normalize(text):
    return FILES.sub(lambda match: match[1] + '"' + match[2].replace('\\', '/') + '"', text)


if __name__ == '__main__':
    Path(sys.argv[2]).write_text(normalize(Path(sys.argv[1]).read_text(encoding="utf-8")), encoding="utf-8")
