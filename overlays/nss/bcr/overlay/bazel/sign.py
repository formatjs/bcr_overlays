"""Sign NSS modules using declared runtime libraries."""
import os
from pathlib import Path
import subprocess
import sys


def sign(tool, source, output, libraries):
    # Remote inputs are regular files; $ORIGIN cannot follow local output symlinks.
    environment = dict(os.environ)
    environment["LD_LIBRARY_PATH"] = ":".join(
        sorted({str(Path(library).absolute().parent) for library in libraries})
    )
    subprocess.run(
        [str(Path(tool).absolute()), "-i", str(Path(source).resolve()),
         "-o", str(Path(output).absolute())],
        env=environment,
        check=True,
    )


if __name__ == "__main__":
    sign(*sys.argv[1:4], sys.argv[4:])
