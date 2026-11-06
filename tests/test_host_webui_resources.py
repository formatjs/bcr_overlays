import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'overlays/chromium/tools'))
from import_cpp_layer import host_webui_resource_copy


class HostWebUIResourcesTest(unittest.TestCase):
    def captures(self):
        suffix = '(//build/toolchain/linux:clang_x64_v8_arm64)'
        prefix = 'clang_x64_v8_arm64/'
        root = '//ui/webui/resources:resources_grit'
        build = '//ui/webui/resources:build_grd'
        native = {'targets': {
            root: {'type': 'action', 'script': '//tools/grit/grit.py',
                   'args': ['-i', 'gen/resources.grd'], 'deps': [build],
                   'outputs': ['//out/bazel-import/gen/resources.h',
                               '//out/bazel-import/gen/resources_map.cc',
                               '//out/bazel-import/gen/resources.pak']},
            build: {'type': 'action', 'args': ['--out-grd', 'gen/resources.grd']},
        }}
        host = {'targets': {label + suffix: copy.deepcopy(target)
                            for label, target in native['targets'].items()}}
        target = host['targets'][root + suffix]
        target['args'] = ['-i', prefix + 'gen/resources.grd', '-t', 'linux']
        target['deps'] = [build + suffix]
        target['outputs'] = [path.replace('gen/', prefix + 'gen/') for path in target['outputs']]
        return host, native

    def test_equivalent_host_uses_declared_native_headers(self):
        host, native = self.captures()
        result = host_webui_resource_copy(host, native)
        self.assertEqual(result['outputs'], {
            'clang_x64_v8_arm64/gen/resources.h': 'gen/resources.h',
            'clang_x64_v8_arm64/gen/resources_map.cc': 'gen/resources_map.cc',
        })
        self.assertEqual(set(result['srcs']), {
            '@chromium//native:gen/resources.h', '@chromium//native:gen/resources_map.cc',
        })

    def test_changed_resources_cannot_reuse_native_output(self):
        host, native = self.captures()
        root = '//ui/webui/resources:resources_grit(//build/toolchain/linux:clang_x64_v8_arm64)'
        host['targets'][root]['args'] += ['-D', 'different_branding=true']
        with self.assertRaisesRegex(ValueError, 'configuration differs'):
            host_webui_resource_copy(host, native)

    def test_graph_without_cross_host_needs_no_copy(self):
        _, native = self.captures()
        self.assertIsNone(host_webui_resource_copy(native, native))
