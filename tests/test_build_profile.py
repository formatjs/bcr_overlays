import gzip
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools.ci import profile_buildbuddy
from tools.ci.profile_buildbuddy import summarize, trace_summary


class BuildProfileTest(unittest.TestCase):
    def test_compiler_experiment_report_is_collected_from_workflow_artifact(self):
        report = {'baseline': {'input_entries': 76130}, 'include-scan': {'input_entries': 1000}}
        uri = 'bytestream://formatjs.buildbuddy.io/report'
        for pattern, artifact_path, key in [
            ('Chromium compile input experiment', 'compile-input-experiment/report.json', 'compile_experiment'),
            ('Chromium compile inputs host-blink', 'compile-input-experiment/report.json', 'compile_experiment'),
            ('Chromium cold build linux-amd64', 'linux-amd64/cold-build.json', 'cold_build'),
        ]:
            with self.subTest(pattern=pattern):
                outer = {'pattern': [pattern]}
                artifacts = {'invocation': [{'artifacts': [{
                    'name': 'command-0/' + artifact_path, 'uri': uri}]}]}
                with mock.patch.object(profile_buildbuddy, 'rpc', return_value={'invocation': [outer]}), \
                        mock.patch.object(profile_buildbuddy, 'api_request', side_effect=[
                            io.BytesIO(json.dumps(artifacts).encode()), io.BytesIO(json.dumps(report).encode())]) as api, \
                        mock.patch.dict(os.environ, {'BUILDBUDDY_API_KEY': 'read-only-test-key'}):
                    result = profile_buildbuddy.collect('workflow')
                self.assertEqual(result[key], report)
                api.assert_has_calls([
                    mock.call('GetInvocation', {'selector': {'invocation_id': 'workflow'},
                                               'include_artifacts': True}, 'read-only-test-key'),
                    mock.call('GetFile', {'uri': uri}, 'read-only-test-key'),
                ])

    def test_metrics_preserved_without_command_credentials(self):
        metrics = {'actionSummary': {'actionsCreated': '42123', 'actionsExecuted': '17'},
                   'timingMetrics': {'wallTimeInMs': '12345'}}
        result = summarize({
            'invocationId': 'build', 'command': 'build',
            'structuredCommandLine': [{'secret': 'DO_NOT_EXPORT'}],
            'event': [
                {'buildEvent': {'buildMetrics': metrics}},
                {'buildEvent': {'buildToolLogs': {'log': [
                    {'name': 'command.profile.gz', 'uri': 'bytestream://formatjs.buildbuddy.io/profile'},
                    {'name': 'other.log', 'contents': 'DO_NOT_EXPORT'},
                ]}}},
            ],
        })
        self.assertEqual(result['metrics'], [metrics])
        self.assertEqual(result['profiles'], [
            {'name': 'command.profile.gz', 'uri': 'bytestream://formatjs.buildbuddy.io/profile'}])
        self.assertNotIn('DO_NOT_EXPORT', json.dumps(result))

    def test_trace_summary_keeps_durations_and_phases_without_event_arguments(self):
        events = [
            {'name': 'compile', 'cat': 'action processing', 'ph': 'X', 'ts': 10, 'dur': 40,
             'args': {'command': 'DO_NOT_EXPORT'}},
            {'name': 'analysis', 'cat': 'build phase marker', 'ph': 'X', 'ts': 0, 'dur': 10},
            {'name': 'counter', 'ph': 'C', 'ts': 1, 'dur': 9999},
        ]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'trace.gz'
            with gzip.open(path, 'wt') as output:
                json.dump({'traceEvents': events}, output)
            result = trace_summary(path)
        self.assertEqual([item['dur'] for item in result['longest_events']], [40, 10])
        self.assertEqual([item['dur'] for item in result['phases']], [10])
        self.assertNotIn('DO_NOT_EXPORT', json.dumps(result))
        self.assertNotIn('compile', json.dumps(result))

    def test_trace_summary_preserves_instant_phases_and_selected_resource_samples(self):
        events = [
            {'cat': 'build phase marker', 'name': 'Complete build', 'ph': 'i', 'ts': 9000000},
            {'cat': 'general information', 'name': 'MerkleTreeComputer.buildForSpawn',
             'ph': 'X', 'dur': 500000},
            {'cat': 'Remote execution process wall time', 'ph': 'X', 'dur': 2000000},
            *[{'name': 'CPU usage (Bazel)', 'ph': 'C',
               'args': {'cpu': value, 'command': 'DO_NOT_EXPORT'}} for value in (2, 6)],
            {'name': 'Memory usage (Bazel)', 'ph': 'C', 'args': {'memory': 1024}},
        ]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'trace.json'
            path.write_text(json.dumps({'traceEvents': events}))
            result = trace_summary(path)
        self.assertEqual(result['phases'][0]['name'], 'Complete build')
        self.assertEqual(result['phases'][0]['ph'], 'i')
        self.assertEqual(result['tasks']['merkle'], {'count': 1, 'task_seconds': 0.5})
        self.assertEqual(result['tasks']['worker_execution'], {'count': 1, 'task_seconds': 2})
        self.assertEqual(result['counters']['bazel_cpu'], {
            'samples': 2, 'sample_mean': 4, 'sample_max': 6, 'unit': 'cores'})
        self.assertNotIn('DO_NOT_EXPORT', json.dumps(result))


if __name__ == '__main__':
    unittest.main()
