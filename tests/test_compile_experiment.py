import json
from pathlib import Path
import tempfile
import unittest

from tools.ci.compile.experiment import TARGET, archive_outputs, compile_spawns


class CompileExperimentTest(unittest.TestCase):
    def test_compiler_report_counts_real_inputs_without_exporting_command_or_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'spawns.json'
            other = {'mnemonic': 'CppCompile', 'targetLabel': '//other:library', 'inputs': []}
            probe = {'mnemonic': 'CppCompile',
                     'targetLabel': '//tools/ci/compile:blink_layout_compile_probe',
                     'inputs': [{'path': 'layout_box.cc'}, {'path': 'layout_box.h'}, {'path': 'flags.inc'}],
                     'commandArgs': ['DO_NOT_EXPORT'], 'environmentVariables': ['DO_NOT_EXPORT'],
                     'metrics': {'executionWallTime': '4s'}, 'runner': 'remote'}
            path.write_text(json.dumps(other, indent=2) + '\n' + json.dumps(probe, indent=2) + '\n')
            result = compile_spawns(path)
            self.assertEqual(result['input_entries'], 3)
            self.assertEqual(result['header_inputs'], 2)
            self.assertEqual(result['metrics'], {'executionWallTime': '4s'})
            self.assertNotIn('DO_NOT_EXPORT', json.dumps(result))
            path.write_text(json.dumps(probe) + '\n' + json.dumps(probe))
            with self.assertRaisesRegex(ValueError, 'exactly one'):
                compile_spawns(path)

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


if __name__ == '__main__':
    unittest.main()
