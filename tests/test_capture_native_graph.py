import copy
from pathlib import Path
import tempfile
import unittest

from tools.capture_native_graph import capture, target_closure


class CaptureNativeGraphTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.output = '//out/import/gen/config.json'
        path = self.root / self.output[2:]
        path.parent.mkdir(parents=True)
        path.write_text('{"enabled":true}\n')
        self.project = {
            'build_settings': {'build_dir': '//out/import/'},
            'targets': {
                '//:config': {'type': 'generated_file', 'outputs': [self.output]},
                '//:browser': {'type': 'executable', 'deps': ['//:config'],
                              'cflags': ['-fstack-protector', '-O2'],
                              'cflags_cc': ['-std=c++20'],
                              'outputs': ['//out/import/chrome']},
            },
        }
        self.runtime = {'//:browser': {'runtime_deps': ['./chrome', 'chrome']}}

    def run_capture(self):
        return capture(self.project, self.runtime, self.root, [])

    def test_closure_keeps_host_and_data_dependencies(self):
        host = '//:generator(//toolchain:host)'
        self.project['targets']['//:config']['deps'] = [host]
        self.project['targets'][host] = {'type': 'executable'}
        self.project['targets']['//:unrelated'] = {'type': 'source_set'}
        selected = target_closure(self.project, ['//:browser'])
        self.assertEqual(set(selected['targets']), {'//:browser', '//:config', host})
        self.assertIn('//:unrelated', self.project['targets'])
        del self.project['targets'][host]
        with self.assertRaisesRegex(ValueError, 'missing dependency'):
            target_closure(self.project, ['//:browser'])

    def test_preserves_flags_generated_contents_and_runtime(self):
        result = self.run_capture()
        browser = result['targets']['//:browser']
        self.assertEqual(result['pool'][browser['cflags']['pool']],
                         ['-fstack-protector', '-O2'])
        self.assertEqual(result['pool'][browser['cflags_cc']['pool']], ['-std=c++20'])
        self.assertEqual(result['generated_files'][self.output], '{"enabled":true}\n')
        self.assertEqual(result['runtime_files']['//:browser'], ['//out/import/chrome'])

    def test_rejects_missing_dependency_or_output_producer(self):
        self.project['targets']['//:browser']['deps'].append('//:absent')
        with self.assertRaisesRegex(ValueError, 'missing dependency'):
            self.run_capture()
        self.project['targets']['//:browser']['deps'].pop()
        self.runtime['//:browser']['runtime_deps'].append('icudtl.dat')
        with self.assertRaisesRegex(ValueError, 'missing runtime producer'):
            self.run_capture()

    def test_rejects_duplicate_producer_and_path_escape(self):
        self.project['targets']['//:other'] = copy.deepcopy(self.project['targets']['//:config'])
        with self.assertRaisesRegex(ValueError, 'duplicate output'):
            self.run_capture()
        del self.project['targets']['//:other']
        self.project['targets']['//:config']['outputs'] = ['//out/import/../../secret']
        with self.assertRaisesRegex(ValueError, 'invalid output path'):
            self.run_capture()

    def test_requires_explicit_host_path_mapping(self):
        self.project['targets']['//:browser']['libs'] = ['/tmp/compiler/lib/builtins.a']
        with self.assertRaisesRegex(ValueError, 'unmapped host path'):
            self.run_capture()
        result = capture(self.project, self.runtime, self.root,
                         [('/tmp/compiler', '$LLVM_ROOT')])
        index = result['targets']['//:browser']['libs']['pool']
        self.assertEqual(result['pool'][index], ['$LLVM_ROOT/lib/builtins.a'])

    def test_captures_gn_time_inputs_without_action_producers(self):
        name = '//out/import/gen/source_list.rsp'
        (self.root / name[2:]).write_text('"../../source with spaces.mojom"')
        self.project['targets']['//:browser']['inputs'] = [name]
        result = self.run_capture()
        self.assertEqual(result['generated_files'][name],
                         '"../../source with spaces.mojom"')
        (self.root / name[2:]).unlink()
        with self.assertRaisesRegex(ValueError, 'unproduced generated input unavailable'):
            self.run_capture()

    def test_declared_sdk_runtime_preserves_source_and_digest(self):
        import hashlib
        source = '//sdk/dbghelp.dll'
        output = '//out/import/dbghelp.dll'
        binary = b'MZ\x00\xffSDK runtime'
        path = self.root / source[2:]
        path.parent.mkdir()
        path.write_bytes(binary)
        self.runtime['//:browser']['runtime_deps'].append('dbghelp.dll')
        self.project['targets']['//:browser']['inputs'] = [output]
        result = capture(self.project, self.runtime, self.root, [],
                         runtime_inputs={output: source})
        self.assertEqual(result['runtime_inputs'][output], {
            'source': source, 'sha256': hashlib.sha256(binary).hexdigest(),
        })
        self.runtime['//:browser']['runtime_deps'].append('undeclared.dll')
        with self.assertRaisesRegex(ValueError, 'missing runtime producer'):
            capture(self.project, self.runtime, self.root, [],
                    runtime_inputs={output: source})

    def test_captures_gn_time_generator_output_manifest(self):
        output = '//out/import/gen/dawn.expected_outputs'
        (self.root / output[2:]).write_text('include/dawn/webgpu.h\n')
        self.project['targets']['//:browser']['args'] = [
            '--expected-outputs-file', 'gen/dawn.expected_outputs',
        ]
        result = self.run_capture()
        self.assertEqual(result['generated_files'][output], 'include/dawn/webgpu.h\n')

    def test_rejects_unused_or_escaping_sdk_runtime_inputs(self):
        output = '//out/import/dbghelp.dll'
        with self.assertRaisesRegex(ValueError, 'unused runtime input'):
            capture(self.project, self.runtime, self.root, [],
                    runtime_inputs={output: '//sdk/dbghelp.dll'})
        self.runtime['//:browser']['runtime_deps'].append('dbghelp.dll')
        with self.assertRaisesRegex(ValueError, 'invalid runtime input source'):
            capture(self.project, self.runtime, self.root, [],
                    runtime_inputs={output: '//sdk/../../outside.dll'})


if __name__ == '__main__':
    unittest.main()
