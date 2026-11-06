import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'overlays/chromium/tools'))
from import_cpp_layer import reuse_host_graphics


class HostGraphicsReuseTest(unittest.TestCase):
    def capture(self, label='//third_party/angle:libEGL', kind='shared_library'):
        suffix = '(//build/toolchain/linux:clang_x64_v8_arm64)'
        native = {
            'type': kind,
            'sources': ['//third_party/angle/src/libEGL/libEGL.cpp'],
            'cflags_cc': {'pool': 0},
            'outputs': ['//out/bazel-import/libEGL.so'],
            'deps': ['//third_party/angle:angle_common'],
        }
        target = copy.deepcopy(native)
        target['outputs'] = ['//out/bazel-import/clang_x64_v8_arm64/libEGL.so']
        target['deps'] = [dependency + suffix for dependency in native['deps']]
        library = {
            'name': 'host_egl', 'kind': kind, 'srcs': ['egl.cpp'],
            'hdrs': ['egl.h'], 'copts': ['-std=c++20'], 'defines': [],
            'includes': ['gen'], 'linkopts': [], 'deps': [':host_common'],
            'outputs': ['clang_x64_v8_arm64/libEGL.so'],
        }
        return ({'targets': {label + suffix: target}, 'pool': [['-std=c++20']]},
                {'targets': {label: native}, 'pool': [['-std=c++20']]},
                {label + suffix: library}, {label: ':native_egl'})

    def test_matching_shared_library_keeps_host_runtime_path(self):
        capture, native, libraries, providers = self.capture()
        self.assertEqual(reuse_host_graphics(capture, native, libraries, providers), 1)
        library = next(iter(libraries.values()))
        self.assertEqual(library['kind'], 'shared_library_import')
        self.assertEqual(library['shared_library'], '@chromium//native:libEGL.so')
        self.assertEqual(library['outputs'], ['clang_x64_v8_arm64/libEGL.so'])
        self.assertEqual(library['srcs'], [])

    def test_configuration_or_source_changes_keep_separate_build(self):
        for field, value in [
            ('cflags_cc', ['-std=c++20', '-fno-rtti']),
            ('defines', ['DIFFERENT_PLATFORM_FEATURE']),
            ('sources', ['//third_party/angle/src/other.cpp']),
            ('ldflags', ['-Wl,--no-undefined']),
        ]:
            with self.subTest(field=field):
                capture, native, libraries, providers = self.capture()
                next(iter(capture['targets'].values()))[field] = value
                original = copy.deepcopy(libraries)
                self.assertEqual(reuse_host_graphics(capture, native, libraries, providers), 0)
                self.assertEqual(libraries, original)

    def test_v8_layout_is_never_replaced_by_native_graphics_reuse(self):
        capture, native, libraries, providers = self.capture('//v8:v8_base_without_compiler')
        original = copy.deepcopy(libraries)
        self.assertEqual(reuse_host_graphics(capture, native, libraries, providers), 0)
        self.assertEqual(libraries, original)

    def test_static_library_uses_existing_native_provider(self):
        capture, native, libraries, providers = self.capture(kind='static_library')
        self.assertEqual(reuse_host_graphics(capture, native, libraries, providers), 1)
        library = next(iter(libraries.values()))
        self.assertEqual(library['kind'], 'group')
        self.assertEqual(library['deps'], ['@chromium//native:native_egl'])
        self.assertEqual(library['srcs'], [])

    def test_matching_fontconfig_uses_native_configuration(self):
        label = '//third_party/fontconfig:fontconfig'
        capture, native, libraries, _ = self.capture(label, kind='static_library')
        self.assertEqual(reuse_host_graphics(capture, native, libraries,
                                            {label: ':fonts_fontconfig'}), 1)
        library = next(iter(libraries.values()))
        self.assertEqual(library['deps'], ['@chromium//native:fonts_fontconfig'])
        self.assertEqual(library['srcs'], [])
