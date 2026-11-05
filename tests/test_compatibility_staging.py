"""Compatibility entries preserve tested files and remain immutable."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.stage_compatibility_modules import (
    add_presubmit, integrity, patch_paths, prepare_entry, registry_url, stage_entries,
)


class CompatibilityStagingTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.workspace = self.root / 'workspace'
        self.repository = self.root / 'external/sample+'
        self.upstream = self.root / 'upstream'
        self.entry = self.upstream / 'modules/sample/1.0'
        self.entry.mkdir(parents=True)
        self.repository.mkdir(parents=True)
        (self.workspace / 'patches').mkdir(parents=True)
        self.patch = b'--- types.h\n+++ types.h\n@@ -1 +1 @@\n-old\n+upstream\n'
        (self.entry / 'patches').mkdir()
        (self.entry / 'patches/upstream.patch').write_bytes(self.patch)
        self.source = {
            'url': 'https://example.invalid/sample.tar.gz',
            'integrity': integrity(b'archive'),
            'overlay': {'BUILD.bazel': integrity(b'original build')},
            'patch_strip': 0,
            'patches': {'upstream.patch': integrity(self.patch)},
        }
        data = json.dumps(self.source).encode()
        (self.entry / 'source.json').write_bytes(data)
        self.hashes = {registry_url(str(self.upstream), 'modules/sample/1.0/source.json'):
                       hashlib.sha256(data).hexdigest()}
        (self.entry.parent / 'metadata.json').write_text(json.dumps({
            'homepage': 'https://example.invalid/sample', 'maintainers': [{'name': 'Upstream'}],
            'repository': ['https://example.invalid'],
            'versions': ['1.0'], 'yanked_versions': {},
        }))
        (self.repository / 'MODULE.bazel').write_text(
            'module(name = "sample", version = "1.0")\n'
            'bazel_dep(name = "rules_cc", version = "0.1")\n'
            'bazel_dep(name = "googletest", version = "0.9", dev_dependency = True)\n')
        (self.repository / 'BUILD.bazel').write_text('patched build\n')
        (self.repository / 'types.h').write_text('upstream\n')
        (self.workspace / 'patches/local.patch').write_bytes(
            b'--- a/BUILD.bazel\n+++ b/BUILD.bazel\n@@ -1 +1 @@\n-old\n+patched build\n')
        self.override = {
            'kind': 'single_version_override', 'patch_strip': 1,
            'patches': ['//patches:local.patch'],
        }

    def prepare(self, **options):
        return prepare_entry(
            self.workspace, self.repository.parent, str(self.upstream), self.hashes,
            'sample', '1.0', options.get('override', self.override), 'chromium142',
            {'rules_cc': '0.2.26', 'googletest': '1.17'})

    def test_effective_overlay_replaces_patch_replay_and_pins_dependencies(self):
        entry = self.prepare()
        target = self.root / 'published'
        stage_entries([entry], target)
        version = target / 'modules/sample/1.0.chromium142'
        source = json.loads((version / 'source.json').read_text())
        self.assertEqual(source['url'], self.source['url'])
        self.assertEqual(source['integrity'], self.source['integrity'])
        self.assertEqual(source['patches'], {})
        self.assertEqual((version / 'overlay/BUILD.bazel').read_text(), 'patched build\n')
        self.assertEqual((version / 'overlay/types.h').read_text(), 'upstream\n')
        module = (version / 'MODULE.bazel').read_text()
        self.assertIn('version = "1.0.chromium142"', module)
        self.assertIn('name = "rules_cc", version = "0.2.26"', module)
        self.assertIn('name = "googletest", version = "0.9", dev_dependency = True', module)
        self.assertEqual(module, (version / 'overlay/MODULE.bazel').read_text())
        for path, expected in source['overlay'].items():
            self.assertEqual(integrity((version / 'overlay' / path).read_bytes()), expected)
        self.assertEqual(json.loads((version.parent / 'metadata.json').read_text())['maintainers'],
                         [{'name': 'Upstream'}])

    def test_archive_override_keeps_its_archive_without_upstream_source_patches(self):
        override = dict(self.override, kind='archive_override',
                        urls=['https://example.invalid/override.tar.gz'],
                        integrity=integrity(b'override'), strip_prefix='override')
        entry = self.prepare(override=override)
        self.assertEqual(entry['source']['url'], override['urls'][0])
        self.assertEqual(entry['source']['integrity'], override['integrity'])
        self.assertNotIn('types.h', entry['overlay'])

    def test_nasm_consumers_keep_the_tested_checker_dependency(self):
        path = self.repository / 'MODULE.bazel'
        path.write_text(path.read_text() + 'bazel_dep(name = "rules_nasm", version = "0.5.0")\n')
        with self.assertRaisesRegex(ValueError, 'missing tested rules_cc_autoconf'):
            self.prepare()
        entry = prepare_entry(
            self.workspace, self.repository.parent, str(self.upstream), self.hashes,
            'sample', '1.0', self.override, 'chromium142',
            {'rules_cc_autoconf': '0.35.0'})
        self.assertIn('bazel_dep(name = "rules_cc_autoconf", version = "0.35.0")', entry['module'])
        self.assertEqual(entry['module'].encode(), entry['overlay']['MODULE.bazel'])
        self.assertEqual(entry['provenance']['added_dependencies'], {'rules_cc_autoconf': '0.35.0'})

    def test_presubmit_consumer_is_stamped_and_included_in_verified_overlay(self):
        source = self.root / 'consumer'
        source.mkdir()
        (source/'.bazelrc').write_text('build --jobs=2\n')
        (source/'.bazelversion').write_text('9.2.0\n')
        consumer = dict(module='module(name = "consumer")\n'
                        'bazel_dep(name = "sample", version = "1.0")\n',
                        targets=['@sample//:sample'])
        entry = self.prepare()
        add_presubmit(entry, consumer, source)
        target = self.root / 'registry'
        stage_entries([entry], target)
        version = target / 'modules/sample/1.0.chromium142'
        module = (version/'overlay/bcr_test/MODULE.bazel').read_text()
        self.assertIn('version = "1.0.chromium142"', module)
        job = json.loads((version/'presubmit.yml').read_text())['bcr_test_module']
        self.assertEqual(job['module_path'], 'bcr_test')
        self.assertEqual(job['matrix']['bazel'], ['9.2.0'])
        self.assertEqual(job['tasks']['linux']['build_targets'], ['//:libraries'])
        metadata = json.loads((version/'source.json').read_text())
        self.assertEqual(metadata['integrity'], self.source['integrity'])
        for path, expected in metadata['overlay'].items():
            self.assertEqual(integrity((version/'overlay'/path).read_bytes()), expected)
        with self.assertRaisesRegex(ValueError, 'must belong'):
            add_presubmit(self.prepare(), dict(consumer, targets=['@other//:library']), source)

    def test_registry_and_patch_integrity_fail_closed(self):
        (self.entry / 'patches/upstream.patch').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'patch integrity mismatch'):
            self.prepare()
        (self.entry / 'source.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'registry integrity mismatch'):
            self.prepare()

    def test_snapshot_is_immutable_and_existing_entries_are_not_overwritten(self):
        entry = self.prepare()
        (self.repository / 'BUILD.bazel').write_text('later edit\n')
        target = self.root / 'published'
        target.mkdir()
        (target / 'bazel_registry.json').write_text('{"mirrors": []}\n')
        stage_entries([entry], target)
        artifact = target / 'modules/sample/1.0.chromium142/overlay/BUILD.bazel'
        self.assertEqual(artifact.read_text(), 'patched build\n')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            stage_entries([entry], target)
        self.assertEqual((target / 'bazel_registry.json').read_text(), '{"mirrors": []}\n')

    def test_missing_escaping_and_executable_files_are_rejected(self):
        path = self.repository / 'BUILD.bazel'
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'missing file'):
            self.prepare()
        outside = self.root / 'outside'
        outside.write_text('outside')
        path.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'missing file'):
            self.prepare()
        path.unlink()
        path.write_text('patched build\n')
        executable = self.repository / 'types.h'
        executable.chmod(0o755)
        with self.assertRaisesRegex(ValueError, 'executable change'):
            self.prepare()

    def test_patch_enumeration_handles_recount_and_missing_final_newline(self):
        patch = (b'--- a/source.cc\n+++ b/source.cc\n@@ -1,99 +1,99 @@\n'
                 b'--- old\n+++ new\n same')
        self.assertEqual(patch_paths(patch, 1), ['source.cc'])


if __name__ == '__main__':
    unittest.main()
