"""Independent module publication and immutable registry behavior."""

import json
from pathlib import Path
import tempfile
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
