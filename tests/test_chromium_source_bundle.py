import hashlib
import ast
import base64
import json
from pathlib import Path
import tempfile
import unittest

from tools.bundle_chromium_sources import PREFIX, module_template, stage_chromium, support_files, write_support


class ChromiumSourceBundleTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.workspace = self.root/'workspace'
        files = {
            'build/dependencies.bzl': '_OVERLAYS = ["chromium", "v8"]\n'
                'source = Label("//:overlays.json")\n'
                'manifest = Label("//overlays/chromium:native/platform_runtime.json")\n',
            'build/fetch.bzl': 'template = Label("//build:source.BUILD.bazel")\n',
            'build/BUILD.bazel': 'exports_files(["fetch.bzl"])\n',
            'overlays.json': '{}\n',
            'MODULE.bazel': 'module(name = "chromium_build", version = "142.0.7444.59")\n'
                'bazel_dep(name = "sample", version = "1.0")\n'
                'archive_override(module_name = "sample", urls = ["https://example.invalid/source"])\n'
                'sources = use_extension("//build:dependencies.bzl", "chromium_dependencies")\n'
                'use_repo(sources, "chromium", "v8")\n'
                'register_toolchains("@llvm//toolchain:all")\n'
                'rust = use_extension("//overlays/chromium/bcr/overlay/native/rust:extensions.bzl", "chromium_rust")\n',
            'overlays/v8/bcr/overlay/BUILD.bazel': 'alias(name = "engine", actual = "@chromium//native:browser_v8")\n',
            'overlays/v8/bcr/patches/dependencies.patch': 'exact upstream patch bytes\n',
            'overlays/chromium/native/platform_runtime.json': '{"packages": []}\n',
            'overlays/chromium/bcr/overlay/native/quiche_repository.BUILD.bazel': 'exports_files([])\n',
            'overlays/chromium/tests/browser_bcr/MODULE.bazel': 'module(name = "browser_consumer")\n',
            'overlays/chromium/tests/browser_bcr/BUILD.bazel': 'filegroup(name = "browser")\n',
            'overlays/chromium/tests/browser_bcr/.bazelrc': 'build --jobs=4\n',
            'overlays/chromium/tests/browser_bcr/.bazelversion': '9.2.0\n',
        }
        for name, content in files.items():
            path = self.workspace/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)

    def test_bundle_relocates_workspace_labels_without_rewriting_overlay_code(self):
        files = support_files(self.workspace)
        dependencies = files[PREFIX + '/build/dependencies.bzl'].decode()
        self.assertNotIn('"chromium",', dependencies)
        self.assertIn('"//native/support:overlays.json"', dependencies)
        self.assertIn('"//native/support/overlays/chromium:native/platform_runtime.json"', dependencies)
        self.assertIn(b'"//native/support/build:source.BUILD.bazel"', files[PREFIX + '/build/fetch.bzl'])
        path = 'overlays/v8/bcr/overlay/BUILD.bazel'
        self.assertEqual(files[PREFIX + '/' + path], (self.workspace/path).read_bytes())
        self.assertNotIn(PREFIX + '/overlays/chromium/bcr/overlay/native/browser_sources.bzl', files)

    def test_written_bundle_is_complete_integrity_recorded_and_immutable(self):
        files = support_files(self.workspace)
        destination = self.root/'bundle'
        write_support(files, destination)
        manifest = json.loads((destination/'support_manifest.json').read_text())
        self.assertEqual(set(manifest), set(files))
        for name, expected in manifest.items():
            self.assertEqual(hashlib.sha256((destination/name).read_bytes()).hexdigest(), expected)
        with self.assertRaisesRegex(ValueError, 'already exists'):
            write_support(files, destination)

    def test_external_symlink_is_rejected_instead_of_followed(self):
        secret = self.root/'outside'
        secret.write_text('not part of the module')
        (self.workspace/'build/escape.bzl').symlink_to(secret)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            support_files(self.workspace)

    def test_published_module_uses_registry_versions_and_its_own_source_extension(self):
        module = module_template(self.workspace, '142.0.7444.59', {'sample': '1.0.chromium142'})
        calls = [node.value for node in ast.parse(module).body
                 if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)]
        functions = {call.func.id for call in calls}
        declaration = next(call for call in calls if call.func.id == 'module')
        self.assertEqual({key.arg: ast.literal_eval(key.value) for key in declaration.keywords}['name'], 'chromium')
        dependency = next(call for call in calls if call.func.id == 'bazel_dep')
        self.assertEqual({key.arg: ast.literal_eval(key.value) for key in dependency.keywords}['version'], '1.0.chromium142')
        self.assertNotIn('archive_override', functions)
        self.assertNotIn('register_toolchains', functions)
        self.assertIn('//native/support/build:dependencies.bzl', module)
        self.assertIn('//native/rust:extensions.bzl', module)
        repositories = next(call for call in calls if call.func.id == 'use_repo')
        self.assertEqual([ast.literal_eval(arg) for arg in repositories.args[1:]], ['v8'])

    def test_registry_entry_contains_complete_bundle_with_integrity_and_cannot_be_replaced(self):
        source = self.workspace/'overlays/chromium/bcr'
        for name in ['abseil-cpp', 'boringssl', 'chromium']:
            directory = self.workspace/'overlays'/name/'bcr'
            directory.mkdir(parents=True, exist_ok=True)
            (directory/'metadata.json').write_text(json.dumps({
                'versions': ['142.0.7444.59'], 'yanked_versions': {},
                'maintainers': [{'github': 'maintainer'}],
                'repository': ['https://example.invalid']}))
        (source/'MODULE.bazel').write_text('module(name = "chromium", version = "")\n')
        (source/'overlay/MODULE.bazel').write_text((source/'MODULE.bazel').read_text())
        pin = {'url': 'https://example.invalid/chromium.tar.xz', 'integrity': 'sha256-pinned'}
        (source/'source.json').write_text(json.dumps(pin))
        (source/'presubmit.yml').write_text('tasks: {}\n')
        registry = self.root/'registry'
        staged = stage_chromium(self.workspace, registry, '142.0.7444.59')
        manifest = json.loads((staged/'source.json').read_text())
        self.assertEqual(manifest['integrity'], pin['integrity'])
        self.assertEqual(manifest['url'], pin['url'])
        self.assertIn(PREFIX + '/build/dependencies.bzl', manifest['overlay'])
        presubmit = json.loads((staged/'presubmit.yml').read_text())['bcr_test_module']
        self.assertIn(presubmit['module_path'] + '/MODULE.bazel', manifest['overlay'])
        self.assertEqual(presubmit['tasks']['browser']['build_targets'], ['//:browser'])
        for path, expected in manifest['overlay'].items():
            self.assertEqual('sha256-' + base64.b64encode(
                hashlib.sha256((staged/'overlay'/path).read_bytes()).digest()).decode(), expected)
        module = (staged/'MODULE.bazel').read_text()
        self.assertEqual(module, (staged/'overlay/MODULE.bazel').read_text())
        self.assertNotIn('archive_override(', module)
        self.assertIn('version = "142.0.7444.59"', module)
        before = (staged/'source.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'already exists'):
            stage_chromium(self.workspace, registry, '142.0.7444.59')
        self.assertEqual((staged/'source.json').read_bytes(), before)
