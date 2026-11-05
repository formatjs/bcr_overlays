"""Independent module publication and immutable registry behavior."""

import json
from pathlib import Path
import tempfile
import subprocess
import unittest

from tools.stage_bcr_entry import stage_entry


class StagingTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.registry = self.root / "registry"

    def source(self, module):
        source = self.root / module
        (source / "overlay").mkdir(parents=True)
        template = f'module(name = "{module}", version = "")\n'
        (source / "MODULE.bazel").write_text(template)
        (source / "overlay/MODULE.bazel").write_text(template)
        (source / "overlay/payload.txt").write_text(module)
        (source / "metadata.json").write_text(json.dumps({
            "versions": ["1.0"], "yanked_versions": {},
            "maintainers": [{"github": "maintainer"}],
            "repository": ["https://example.test"],
        }))
        (source / "source.json").write_text(json.dumps({
            "url": f"https://example.test/{module}.tar.gz",
            "integrity": "sha256-" + "A" * 43 + "=",
            "strip_prefix": module,
        }))
        (source / "presubmit.yml").write_text("tasks: {}\n")
        return source

    def test_modules_publish_independently_at_same_version(self):
        for module in ("alpha", "beta"):
            with self.subTest(module=module):
                entry = stage_entry(self.source(module), self.registry, module, "1.0")
                self.assertEqual((entry / "overlay/payload.txt").read_text(), module)
                self.assertEqual((entry / "MODULE.bazel").read_text(),
                                 f'module(name = "{module}", version = "1.0")\n')
        self.assertEqual(
            {path.name for path in (self.registry / "modules").iterdir()},
            {"alpha", "beta"},
        )

    def test_rejects_wrong_module_and_path_traversal_without_writing(self):
        source = self.source("alpha")
        for module, version in (("beta", "1.0"), ("../alpha", "1.0"), ("alpha", "../1.0")):
            with self.subTest(module=module, version=version):
                with self.assertRaises(ValueError):
                    stage_entry(source, self.registry, module, version)
                self.assertFalse(self.registry.exists())

    def test_rejects_missing_maintainers_before_writing_registry(self):
        source = self.source("alpha")
        metadata = json.loads((source / "metadata.json").read_text())
        for maintainers in (None, [], {"github": "maintainer"}):
            with self.subTest(maintainers=maintainers):
                metadata["maintainers"] = maintainers
                (source / "metadata.json").write_text(json.dumps(metadata))
                with self.assertRaisesRegex(ValueError, "at least one maintainer"):
                    stage_entry(source, self.registry, "alpha", "1.0")
                self.assertFalse(self.registry.exists())

    def test_published_entry_remains_immutable_after_source_changes(self):
        source = self.source("alpha")
        stage_entry(source, self.registry, "alpha", "1.0")
        before = {path.relative_to(self.registry): path.read_bytes()
                  for path in self.registry.rglob("*") if path.is_file()}
        (source / "overlay/payload.txt").write_text("changed")
        with self.assertRaises(ValueError):
            stage_entry(source, self.registry, "alpha", "1.0")
        after = {path.relative_to(self.registry): path.read_bytes()
                 for path in self.registry.rglob("*") if path.is_file()}
        self.assertEqual(after, before)

    def test_repository_allowlist_accepts_github_and_rejects_similar_prefixes(self):
        for index, repository in enumerate(("github:owner/repo", "https://github.com/owner/repo/")):
            source = self.source("alpha" + str(index))
            metadata = json.loads((source / "metadata.json").read_text())
            metadata["repository"] = [repository]
            (source / "metadata.json").write_text(json.dumps(metadata))
            info = json.loads((source / "source.json").read_text())
            info["url"] = "https://github.com/owner/repository/archive/1.0.tar.gz"
            (source / "source.json").write_text(json.dumps(info))
            target = self.registry / str(index)
            with self.assertRaisesRegex(ValueError, "source URL not allowed"):
                stage_entry(source, target, "alpha" + str(index), "1.0")
            self.assertFalse(target.exists())
            info["url"] = "https://github.com/owner/repo/archive/1.0.tar.gz"
            (source / "source.json").write_text(json.dumps(info))
            stage_entry(source, target, "alpha" + str(index), "1.0")

    def test_rejects_links_to_unpublished_files_and_directories(self):
        source = self.source("alpha")
        outside = self.root / "unpublished"
        outside.mkdir()
        payload = outside / "payload.txt"
        payload.write_text("not part of this release")
        link = source / "overlay/tool_output"
        for destination in (outside, payload):
            with self.subTest(destination=destination):
                link.symlink_to(destination)
                with self.assertRaisesRegex(ValueError, "symlink in published source"):
                    stage_entry(source, self.registry, "alpha", "1.0")
                self.assertFalse(self.registry.exists())
                self.assertEqual(payload.read_text(), "not part of this release")
                link.unlink()

    def test_staged_patch_applies_with_requested_strip_depth(self):
        source = self.source("alpha")
        info = json.loads((source / "source.json").read_text())
        info["patch_strip"] = 2
        (source / "source.json").write_text(json.dumps(info))
        (source / "patches").mkdir()
        (source / "patches/fix.patch").write_text(
            "--- a/vendor/value.txt\n+++ b/vendor/value.txt\n"
            "@@ -1 +1 @@\n-before\n+after\n")
        entry = stage_entry(source, self.registry, "alpha", "1.0")
        staged = json.loads((entry / "source.json").read_text())
        extracted = self.root / "upstream"
        extracted.mkdir()
        (extracted / "value.txt").write_text("before\n")
        for name in staged["patches"]:
            subprocess.run(["patch", "--batch", f'-p{staged["patch_strip"]}',
                            "-i", str(entry / "patches" / name)],
                           cwd=extracted, check=True, capture_output=True)
        self.assertEqual((extracted / "value.txt").read_text(), "after\n")

    def test_planned_overlays_cannot_be_staged(self):
        root = Path(__file__).resolve().parents[1]
        catalog = json.loads((root / "overlays.json").read_text())
        for module, overlay in catalog["overlays"].items():
            if overlay["status"] != "planned":
                continue
            with self.subTest(module=module):
                with self.assertRaisesRegex(ValueError, "missing from source metadata"):
                    stage_entry(root / overlay["path"] / "bcr", self.registry, module, "1.0")
                self.assertFalse(self.registry.exists())


if __name__ == "__main__":
    unittest.main()
