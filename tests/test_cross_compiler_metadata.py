# SPDX-License-Identifier: MIT
"""Cross-target metadata must preserve compiler features and generator ABIs."""
from pathlib import Path
import ast
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'overlays/chromium/tools'))
from import_cpp_layer import REUSED, header_resolver, reuse_host_targets, foreach_arguments
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

    def test_cross_snapshot_flatbuffers_output_uses_toolchain_tree(self):
        source = '//third_party/tflite/cache.fbs'
        for prefix in ['', 'clang_x64_v8_arm64/']:
            arguments = foreach_arguments(
                ['-o', '{{source_gen_dir}}', '{{source}}'], source,
                ['//out/bazel-import/' + prefix + 'gen/third_party/tflite/cache_generated.h'])
            self.assertEqual(arguments, ['-o', prefix + 'gen/third_party/tflite',
                                         '../../third_party/tflite/cache.fbs'])

    def test_objcxx_preserves_arc_without_captured_sdk_path(self):
        options, _ = compiler_configuration({}, {
            'cflags': ['-isysroot', '/captured/sdk', '-Xclang', '-debug-info-kind=limited'],
            'cflags_cc': ['-std=c++20'],
            'cflags_objcc': ['-fobjc-arc', '-fno-objc-arc-exceptions'], 'defines': [],
        }, 'cflags_objcc')
        self.assertEqual(options, ['-Xclang', '-debug-info-kind=limited',
                                   '-fobjc-arc', '-fno-objc-arc-exceptions'])

    def test_unknown_frontend_feature_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'unmapped Clang target feature'):
            compiler_configuration({}, {
                'cflags': ['-Xclang', '-target-feature', '-Xclang', '+unknown'],
                'cflags_cc': [], 'defines': [],
            })

    def test_msvc_flags_preserve_crt_and_constructor_debug_info(self):
        flags, _ = compiler_configuration({}, {
            'cflags': ['/WX', '/MT', '-Xclang', '-fuse-ctor-homing',
                       '-mllvm', '-pick-merged-source-locations', '-fmsc-version=1934'],
            'cflags_cc': ['/std:c++20', '-I../../third_party/libc++/src/include'],
            'defines': [],
        })
        self.assertEqual(flags, ['/MT', '/clang:-Xclang', '/clang:-fuse-ctor-homing',
                                 '/clang:-mllvm', '/clang:-pick-merged-source-locations',
                                 '/std:c++20', '/EHs-c-'])

    def test_cross_snapshot_keeps_its_v8_and_blink_libraries(self):
        host = '(//build/toolchain/linux:clang_x64)'
        snapshot = '(//build/toolchain/linux:clang_x64_v8_arm64)'
        base = '//base:base'
        v8 = '//v8:v8_base_without_compiler'
        blink = '//third_party/blink/renderer/core:core'
        flags = '//build:branding_buildflags'
        reused = {base: ':base', v8: ':v8_target', blink: ':blink_target',
                  flags: ':all_buildflags'}
        provided = set()
        targets = {label + suffix: {} for label in (base, v8, blink, flags)
                   for suffix in (host, snapshot)}
        reuse_host_targets(targets, reused, provided)
        self.assertEqual(reused[flags + host], ':all_buildflags')
        self.assertEqual(reused[flags + snapshot], ':all_buildflags')
        self.assertEqual(reused[base + host], '@chromium//native:base')
        self.assertEqual(reused[base + snapshot], '@chromium//native:base')
        self.assertEqual(reused[v8 + host], '@chromium//native:v8_target')
        self.assertNotIn(v8 + snapshot, reused)
        self.assertNotIn(blink + snapshot, reused)
        self.assertEqual(reused[v8], ':v8_target')

    def test_rust_host_tools_use_linux_allocator(self):
        suffix = '(//build/toolchain/linux:clang_x64_for_rust_host_build_tools)'
        labels = ['//build/rust/allocator:allocator_impls_ffi',
                  '//build/rust/allocator:alloc_error_handler_impl_ffi']
        reused = {label: REUSED[label] for label in labels}
        reuse_host_targets({label + suffix: {} for label in labels}, reused, set())
        for label in labels:
            self.assertEqual(reused[label + suffix], '@chromium' + REUSED[label])

    def test_host_library_uses_native_layer_owner(self):
        label = '//components/url_formatter/spoof_checks/common_words:common'
        host = label + '(//build/toolchain/linux:clang_x64)'
        platform = ':blink_platform_e3b8293788f3d44c'
        native = ':ozone_e3b8293788f3d44c'
        reused = {label: platform}
        reuse_host_targets({host: {}}, reused, set(), {label: native})
        self.assertEqual(reused[host], '@chromium//native' + native)
        self.assertEqual(reused[label], platform)

    def test_host_library_without_native_owner_keeps_captured_build(self):
        label = '//components/platform_only:helper'
        host = label + '(//build/toolchain/linux:clang_x64)'
        reused = {label: ':blink_platform_0123456789abcdef'}
        reuse_host_targets({host: {}}, reused, set(), {})
        self.assertNotIn(host, reused)

    def test_cross_snapshot_uses_canonical_host_icu(self):
        suffix = '(//build/toolchain/linux:clang_x64_v8_arm64)'
        labels = ['//third_party/icu:' + name for name in
                  ['icudata', 'icui18n', 'icuuc', 'icuuc_private', 'icuuc_public']]
        reused = dict(REUSED)
        reuse_host_targets({label + suffix: {} for label in labels}, reused, set())
        for label in labels:
            self.assertEqual(reused[label + suffix], '@chromium//third_party/icu:icu')


if __name__ == '__main__':
    unittest.main()
