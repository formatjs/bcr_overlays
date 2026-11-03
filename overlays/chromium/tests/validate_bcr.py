#!/usr/bin/env python3
"""Check source pins and immutable registry staging without network access."""

import base64
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parents[1]))
from tools.stage_bcr_entry import stage_entry


def main():
    source = ROOT / "bcr"
    metadata = json.loads((source / "metadata.json").read_text())
    version = metadata["versions"][-1]
    template = (source / "MODULE.bazel").read_text()
    if template != (source / "overlay/MODULE.bazel").read_text():
        raise ValueError("registry and overlay module templates differ")
    pin = json.loads((source / "source.json").read_text())
    digest = base64.b64decode(pin["integrity"].removeprefix("sha256-"), validate=True)
    if len(digest) != 32:
        raise ValueError("invalid archive SHA-256")
    development = (ROOT / "MODULE.bazel").read_text()
    for value in (pin["url"], pin["strip_prefix"], digest.hex(), version):
        if value not in development:
            raise ValueError("development source pin differs from BCR source pin")

    with tempfile.TemporaryDirectory() as temp:
        registry = Path(temp)
        # An existing entry must survive adding the next version.
        previous = registry / "modules/chromium/0.0.0"
        previous.mkdir(parents=True)
        sentinel = previous / "MODULE.bazel"
        sentinel.write_text("published entry\n")
        (previous.parent / "metadata.json").write_text(json.dumps({
            "versions": ["0.0.0"], "yanked_versions": {"0.0.0": "test entry"}
        }))
        staged = stage_entry(source, registry, "chromium", version)
        manifest = json.loads((staged / "source.json").read_text())
        for kind in ("overlay", "patches"):
            expected = {
                path.relative_to(staged / kind).as_posix():
                    "sha256-" + base64.b64encode(hashlib.sha256(path.read_bytes()).digest()).decode()
                for path in (staged / kind).rglob("*") if path.is_file()
            }
            if expected != manifest[kind]:
                raise ValueError(f"staged {kind} checksums differ")
        if (staged / "MODULE.bazel").read_bytes() != (staged / "overlay/MODULE.bazel").read_bytes():
            raise ValueError("staged module files differ")
        try:
            stage_entry(source, registry, "chromium", version)
        except ValueError:
            pass
        else:
            raise ValueError("staging overwrote an existing version")
        result = json.loads((previous.parent / "metadata.json").read_text())
        if result["versions"] != ["0.0.0", version] or result["yanked_versions"].get("0.0.0") != "test entry":
            raise ValueError("staging lost published metadata")
        if sentinel.read_text() != "published entry\n":
            raise ValueError("staging changed a published entry")
    print(f"BCR staging valid: chromium@{version}")


if __name__ == "__main__":
    main()
