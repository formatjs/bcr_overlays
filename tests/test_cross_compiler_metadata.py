# SPDX-License-Identifier: MIT
"""Cross-target metadata must preserve compiler features and generator ABIs."""
from pathlib import Path
import ast
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'overlays/chromium/tools'))
from import_cpp_layer import header_resolver, reuse_host_targets
from import_base import starlark_literal
from import_mojo_runtime import compiler_configuration
sys.path.pop(0)


class CrossCompilerMetadataTest(unittest.TestCase):
    def test_metadata_keywords_leave_generator_strings_intact(self):
        metadata = {'stage_runtime': True, 'disabled': False, 'optional': None,
                    'arguments': ['--value=true', 'false null "true" \\ true']}
        self.assertEqual(ast.literal_eval(starlark_literal(metadata)), metadata)

    def test_cached_header_lookup_preserves_local_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ['a/local.h', 'b/local.h', 'sdk/shared.h', 'sdk/local.h',
                         'global.h', 'a/global.h']:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            resolve = header_resolver(root, ['sdk'])
            self.assertEqual(resolve('a/source.cc', 'local.h'), 'a/local.h')
            self.assertEqual(resolve('b/source.cc', 'local.h'), 'b/local.h')
            self.assertEqual(resolve('a/source.cc', 'global.h'), 'global.h')
            self.assertEqual(resolve('a/source.cc', 'shared.h'), 'sdk/shared.h')
            self.assertIsNone(resolve('a/source.cc', 'vector'))
            self.assertIsNone(resolve('b/source.cc', 'vector'))

    def test_mte_survives_toolchain_path_filtering(self):
        flags = ['--target=aarch64-linux-gnu', '--sysroot=/captured/sysroot',
                 '-O2', '-Xclang', '-target-feature', '-Xclang', '+mte']
        options, defines = compiler_configuration({}, {
            'cflags': flags, 'cflags_cc': ['-std=c++20'],
            'defines': ['PA_ENABLE_MTE=1', 'CR_SYSROOT_KEY=captured'],
        })
        self.assertEqual(options, ['-O2', '-Xclang', '-target-feature', '-Xclang',
                                   '+mte', '-std=c++20'])
        self.assertEqual(defines, ['PA_ENABLE_MTE=1'])

    def test_unknown_frontend_feature_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'unmapped Clang target feature'):
            compiler_configuration({}, {
                'cflags': ['-Xclang', '-target-feature', '-Xclang', '+unknown'],
                'cflags_cc': [], 'defines': [],
            })

    def test_cross_snapshot_keeps_its_v8_and_blink_libraries(self):
        host = '(//build/toolchain/linux:clang_x64)'
        snapshot = '(//build/toolchain/linux:clang_x64_v8_arm64)'
        base = '//base:base'
        v8 = '//v8:v8_base_without_compiler'
        blink = '//third_party/blink/renderer/core:core'
        reused = {base: ':base', v8: ':v8_target', blink: ':blink_target'}
        provided = set()
        targets = {label + suffix: {} for label in (base, v8, blink)
                   for suffix in (host, snapshot)}
        reuse_host_targets(targets, reused, provided)
        self.assertEqual(reused[base + host], '@chromium//native:base')
        self.assertEqual(reused[base + snapshot], '@chromium//native:base')
        self.assertEqual(reused[v8 + host], '@chromium//native:v8_target')
        self.assertNotIn(v8 + snapshot, reused)
        self.assertNotIn(blink + snapshot, reused)
        self.assertEqual(reused[v8], ':v8_target')


if __name__ == '__main__':
    unittest.main()
