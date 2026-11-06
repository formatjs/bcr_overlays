"""Captured Cocoa sources must reach their owning C++ library."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'overlays/chromium/platforms/darwin_arm64/overlay/native'


class DarwinObjcLayersTest(unittest.TestCase):
    def test_cocoa_sources_compile_and_link_through_owner(self):
        for layer in ['geometry', 'dawn']:
            with self.subTest(layer=layer):
                metadata = ast.parse((NATIVE / (layer + '_sources.bzl')).read_text())
                libraries = next(ast.literal_eval(node.value) for node in metadata.body
                                 if isinstance(node, ast.Assign)
                                 and node.targets[0].id == 'LIBRARIES')
                compiled, libraries_emitted = {}, {}
                environment = {
                    'load': lambda *args, **kwargs: None,
                    'cc_library': lambda **kwargs: libraries_emitted.update({kwargs['name']: kwargs}),
                    'objcxx_library': lambda **kwargs: compiled.update({kwargs['name']: kwargs}),
                    'native': SimpleNamespace(glob=lambda *args: [], alias=lambda **kwargs: None),
                    'LIBRARIES': libraries, 'SHARED_HEADERS': [], 'ACTIONS': [],
                    'METADATA': {}, 'CAPTURED_FILES': {},
                }
                helper = ast.parse((ROOT / 'overlays/chromium/bcr/overlay/native/objcxx.bzl').read_text())
                function = next(node for node in helper.body if isinstance(node, ast.FunctionDef)
                                and node.name == 'chromium_objc_libraries')
                exec(compile(ast.Module(body=[function], type_ignores=[]), '<objc helper>', 'exec'),
                     environment)
                exec((NATIVE / (layer + '.bzl')).read_text(), environment)
                environment['native_' + layer]()
                expected_sources = set()
                for library in libraries.values():
                    for language in ['objc', 'objcxx']:
                        sources = library.get(language + '_srcs', [])
                        if not sources:
                            continue
                        expected_sources.update(sources)
                        name = library['name'] + '_' + language
                        self.assertIn(name, compiled)
                        self.assertEqual(compiled[name]['srcs'], sources)
                        self.assertEqual(compiled[name]['copts'], library[language + '_copts'])
                        self.assertIn(':' + name, libraries_emitted[library['name']]['deps'])
                self.assertTrue(expected_sources)
                self.assertEqual({source for target in compiled.values() for source in target['srcs']},
                                 expected_sources)
