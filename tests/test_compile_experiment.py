import gzip
import json
from pathlib import Path
import tempfile
import unittest

from tools.ci.compile.experiment import TARGET, archive_outputs, compiler_input_diff, compiler_profile


class CompileExperimentTest(unittest.TestCase):
    def test_compact_diff_reports_input_reduction_without_exporting_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'diff.json'
            probe = {'mnemonic': 'CppCompile',
                     'target_label': '//tools/ci/compile:blink_layout_compile_probe',
                     'modified': {'diffs': [{'input_paths': {
                         'old_only': ['unused.h', 'unrelated.h'], 'new_only': ['required.h']}},
                         {'args': {'old': ['DO_NOT_EXPORT'], 'new': []}}]}}
            path.write_text(json.dumps({'spawn_diffs': [probe]}))
            result = compiler_input_diff(path)
            self.assertEqual(result, {'comparison': 'paired', 'input_paths_removed': 2,
                                      'input_paths_added': 1})
            self.assertNotIn('DO_NOT_EXPORT', json.dumps(result))
            probe.pop('modified')
            probe['old_only'] = {'top_level': True}
            path.write_text(json.dumps({'spawn_diffs': [probe]}))
            self.assertEqual(compiler_input_diff(path)['comparison'], 'unpaired')

    def test_compiler_timing_excludes_other_actions_and_nested_wrapper_time(self):
        events = [
            {'ph': 'X', 'cat': 'action processing', 'name': 'Compiling layout_box.cc',
             'tid': 1, 'ts': 100, 'dur': 4000000},
            {'ph': 'X', 'cat': 'Remote execution process wall time', 'name': 'execute',
             'tid': 1, 'ts': 1000000, 'dur': 2000000},
            {'ph': 'X', 'cat': 'general information', 'name': 'MerkleTreeComputer.buildForSpawn',
             'tid': 1, 'ts': 200, 'dur': 500000},
            {'ph': 'X', 'cat': 'Remote execution process wall time', 'name': 'execute',
             'tid': 2, 'ts': 1000000, 'dur': 100000000},
            {'ph': 'X', 'cat': 'action processing', 'name': 'Compiling layout_view.cc',
             'tid': 3, 'ts': 100, 'dur': 3000000},
        ]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'trace.gz'
            with gzip.open(path, 'wt') as output:
                json.dump({'traceEvents': events}, output)
            self.assertEqual(compiler_profile(path), {'action_seconds': 4.0,
                                                     'worker_seconds': 2.0, 'merkle_seconds': 0.5})
            self.assertEqual(compiler_profile(path, 'layout_view.cc'), {
                'action_seconds': 3.0, 'worker_seconds': 0.0, 'merkle_seconds': 0.0})

    def test_archive_proof_requires_successful_local_default_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = root / 'libprobe.a'
            artifact.write_bytes(b'compiler object archive')
            events = root / 'events.json'
            for success, uri, valid in [(True, artifact.as_uri(), True),
                                        (False, artifact.as_uri(), False),
                                        (True, 'bytestream://remote/object', False)]:
                events.write_text('\n'.join(json.dumps(item) for item in [
                    {'id': {'namedSet': {'id': 'archive'}},
                     'namedSetOfFiles': {'files': [{'uri': uri}]}},
                    {'id': {'namedSet': {'id': 'root'}},
                     'namedSetOfFiles': {'fileSets': [{'id': 'archive'}]}},
                    {'id': {'targetCompleted': {'label': TARGET}},
                     'completed': {'success': success,
                                   'outputGroup': [{'name': 'default', 'fileSets': [{'id': 'root'}]}]}},
                ]))
                if valid:
                    digests, _ = archive_outputs(events)
                    self.assertEqual(list(digests), ['libprobe.a'])
                    self.assertEqual(len(digests['libprobe.a']), 64)
                else:
                    with self.assertRaises(ValueError):
                        archive_outputs(events)

    def test_windows_archive_uses_selected_platform_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = root / 'probe.lib'
            artifact.write_bytes(b'COFF archive')
            target = '//tools/ci/compile/windows_arm64:blink-layout-windows-arm64'
            events = root / 'events.json'
            events.write_text('\n'.join(json.dumps(item) for item in [
                {'id': {'namedSet': {'id': 'archive'}},
                 'namedSetOfFiles': {'files': [{'uri': artifact.as_uri()}]}},
                {'id': {'targetCompleted': {'label': target}},
                 'completed': {'success': True, 'outputGroup': [
                     {'name': 'default', 'fileSets': [{'id': 'archive'}]}]}},
            ]))
            digests, _ = archive_outputs(events, target)
            self.assertEqual(list(digests), ['probe.lib'])
            with self.assertRaisesRegex(ValueError, 'did not complete'):
                archive_outputs(events)


if __name__ == '__main__':
    unittest.main()
