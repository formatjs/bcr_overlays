import gzip
import json
from pathlib import Path
import tempfile
import unittest

from tools.ci.profile_buildbuddy import summarize, trace_summary


class BuildProfileTest(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
