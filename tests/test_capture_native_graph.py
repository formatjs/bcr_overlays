import copy
from pathlib import Path
import tempfile
import unittest

from tools.capture_native_graph import capture


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


if __name__ == '__main__':
    unittest.main()
