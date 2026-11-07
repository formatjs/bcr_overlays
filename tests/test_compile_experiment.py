import gzip
import json
import re
from pathlib import Path
import tempfile
import unittest

from tools.ci.compile.experiment import TARGET, archive_outputs, compiler_input_diff, compiler_pattern, compiler_profiles


class CompileExperimentTest(unittest.TestCase):
    def test_compact_source_filter_preserves_selection_and_literal_paths(self):
        sources = ('third_party/blink/renderer/core/css/a.cc',
                   'third_party/blink/renderer/core/layout/b+1.cc')
        old = '.*(' + '|'.join(re.escape(source) for source in sources) + ')'
        compact = compiler_pattern(sources)
        self.assertLess(len(compact), len(old))
        for path in (*sources, 'external/+repo/' + sources[0],
                     'third_party/blink/renderer/core/css/aXcc',
                     'third_party/blink/renderer/core/layout/b1.cc',
                     'third_party/blink/renderer/core/paint/other.cc'):
            with self.subTest(path=path):
                self.assertEqual(bool(re.fullmatch(compact, path)), bool(re.fullmatch(old, path)))

    def test_compiler_source_matching_keeps_generated_binding_prefix_distinct(self):
        events = [
            {'ph': 'X', 'cat': 'action processing', 'name': 'Compiling gen/v8_video_frame.cc [for tool]',
             'tid': 1, 'ts': 0, 'dur': 1000000},
            {'ph': 'X', 'cat': 'action processing', 'name': 'Compiling modules/video_frame.cc [for tool]',
             'tid': 2, 'ts': 0, 'dur': 2000000},
        ]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'trace.gz'
            with gzip.open(path, 'wt') as output:
                json.dump({'traceEvents': events}, output)
            result = compiler_profiles(path, ('video_frame.cc', 'v8_video_frame.cc'))
        self.assertEqual(result['video_frame.cc']['action_seconds'], 2)
        self.assertEqual(result['v8_video_frame.cc']['action_seconds'], 1)

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

    def test_browser_input_diff_excludes_other_probes(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'diff.json'
            path.write_text(json.dumps({'spawn_diffs': [
                {'mnemonic': 'CppCompile',
                 'target_label': '//tools/ci/compile/browser:browser_compile_probe_0',
                 'modified': {'diffs': [{'input_paths': {
                     'old_only': ['a.h', 'b.h', 'c.h'], 'new_only': ['required.h']}}]}},
                {'mnemonic': 'CppCompile',
                 'target_label': '//tools/ci/compile:blink_layout_compile_probe',
                 'old_only': {'top_level': True}},
            ]}))
            self.assertEqual(compiler_input_diff(path, (':browser_compile_probe_0',)), {
                'comparison': 'paired', 'input_paths_removed': 3, 'input_paths_added': 1,
            })
            self.assertEqual(compiler_input_diff(path, (':browser_compile_probe_0',), expected_compiles=1), {
                'comparison': 'paired', 'input_paths_removed': 3, 'input_paths_added': 1,
            })
            with self.assertRaisesRegex(ValueError, 'Expected 2 compiler diffs, found 1'):
                compiler_input_diff(path, (':browser_compile_probe_0',), expected_compiles=2)

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
            # Remote timestamps can extend beyond the client span by several milliseconds.
            {'ph': 'X', 'cat': 'Remote execution process wall time', 'name': 'execute',
             'tid': 3, 'ts': 10100, 'dur': 2999000},
            {'ph': 'X', 'cat': 'Remote execution process wall time', 'name': 'previous action',
             'tid': 3, 'ts': -2000000, 'dur': 2000010},
            {'ph': 'X', 'cat': 'Remote execution process wall time', 'name': 'next action',
             'tid': 3, 'ts': 3000099, 'dur': 2000000},
        ]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'trace.gz'
            with gzip.open(path, 'wt') as output:
                json.dump({'traceEvents': events}, output)
            self.assertEqual(compiler_profiles(path, ('layout_box.cc', 'layout_view.cc')), {
                'layout_box.cc': {'action_seconds': 4.0, 'worker_seconds': 2.0, 'merkle_seconds': 0.5},
                'layout_view.cc': {'action_seconds': 3.0, 'worker_seconds': 2.999, 'merkle_seconds': 0.0},
            })

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
