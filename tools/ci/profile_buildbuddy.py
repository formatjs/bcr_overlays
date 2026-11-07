"""Collect BuildBuddy action counts and sanitized timing summaries for one revision."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
import os
from pathlib import Path
import re
import tempfile
import urllib.request

from tools.ci.buildbuddy_artifacts import API_URL, api_request, invocation_id


RPC_URL = 'https://formatjs.buildbuddy.io/rpc/BuildBuddyService/'


def rpc(method, body):
    request = urllib.request.Request(
        RPC_URL + method, data=json.dumps(body).encode(),
        headers={'Content-Type': 'application/json',
                 'x-buildbuddy-api-key': os.environ['BUILDBUDDY_API_KEY']})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def summarize(invocation):
    result = {key: invocation.get(key) for key in (
        'invocationId', 'command', 'pattern', 'success', 'durationUsec',
        'invocationStatus', 'cacheStats', 'targetConfiguredCount')}
    result['metrics'] = []
    result['profiles'] = []
    for event in invocation.get('event', []):
        build_event = event.get('buildEvent', {})
        if 'buildMetrics' in build_event:
            result['metrics'].append(build_event['buildMetrics'])
        for log in build_event.get('buildToolLogs', {}).get('log', []):
            if 'profile' in log.get('name', '') and log.get('uri', '').startswith('bytestream://'):
                result['profiles'].append({'name': log['name'], 'uri': log['uri']})
    return result


def trace_summary(path):
    with path.open('rb') as source:
        opener = gzip.open if source.read(2) == b'\x1f\x8b' else open
    with opener(path, 'rt') as source:
        trace = json.load(source)
    events = trace.get('traceEvents', [])
    durations = [event for event in events if event.get('ph') == 'X' and event.get('dur', 0) > 0]
    phases = [event for event in durations if event.get('cat') == 'build phase marker']
    longest = sorted(durations, key=lambda event: event['dur'], reverse=True)[:40]
    fields = ('cat', 'ts', 'dur', 'tid')
    return {'phases': [{key: event.get(key) for key in fields} for event in phases],
            'longest_events': [{key: event.get(key) for key in fields} for event in longest]}


def collect(identifier):
    outer = rpc('GetInvocation', {'lookup': {
        'invocationId': identifier, 'fetchChildInvocations': True}})['invocation'][0]
    result = summarize(outer)
    result['children'] = []
    if outer.get('pattern') == ['Chromium compile input experiment']:
        with api_request('GetInvocation', {
                'selector': {'invocation_id': identifier}, 'include_artifacts': True,
        }, os.environ['BUILDBUDDY_API_KEY']) as response:
            invocations = json.load(response).get('invocation', [])
        reports = [artifact for invocation in invocations
                   for artifact in invocation.get('artifacts', [])
                   if artifact.get('name', '').endswith('/compile-input-experiment/report.json')
                   or artifact.get('name') == 'compile-input-experiment/report.json']
        if len(reports) == 1:
            with api_request('GetFile', {'uri': reports[0]['uri']},
                             os.environ['BUILDBUDDY_API_KEY']) as response:
                payload = response.read(4 * 1024 * 1024 + 1)
            if len(payload) > 4 * 1024 * 1024:
                raise ValueError('Compiler experiment report exceeds 4 MiB')
            result['compile_experiment'] = json.loads(payload)
    for child in outer.get('childInvocations', []):
        child_id = child['invocationId']
        full = rpc('GetInvocation', {'lookup': {'invocationId': child_id}})['invocation'][0]
        summary = summarize(full)
        for profile in summary['profiles']:
            request = urllib.request.Request(
                API_URL + 'GetFile', data=json.dumps({'uri': profile['uri']}).encode(),
                headers={'Content-Type': 'application/json',
                         'x-buildbuddy-api-key': os.environ['BUILDBUDDY_API_KEY']})
            with tempfile.TemporaryDirectory(prefix='bb-profile-') as temporary:
                path = Path(temporary) / 'trace.gz'
                with urllib.request.urlopen(request, timeout=120) as response, path.open('wb') as output:
                    size = 0
                    while chunk := response.read(1024 * 1024):
                        size += len(chunk)
                        if size > 256 * 1024 * 1024:
                            raise ValueError('Profile exceeds 256 MiB')
                        output.write(chunk)
                profile['summary'] = trace_summary(path)
            del profile['uri']
        result['children'].append(summary)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9a-f]{40}', args.revision):
        parser.error('--revision must be a full commit SHA')
    repository = os.environ.get('GITHUB_REPOSITORY', 'formatjs/chromium')
    request = urllib.request.Request(
        f'https://api.github.com/repos/{repository}/commits/{args.revision}/status?per_page=100',
        headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN']})
    with urllib.request.urlopen(request, timeout=60) as response:
        statuses = json.load(response)['statuses']
    identifiers = {}
    for status in statuses:
        url = status.get('target_url', '')
        if url.startswith('https://formatjs.buildbuddy.io/invocation/'):
            identifiers.setdefault(status['context'], invocation_id(url))
    args.directory.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {name: executor.submit(collect, identifier)
                   for name, identifier in identifiers.items()}
        results = {}
        for name, future in futures.items():
            try:
                results[name] = future.result()
            except Exception as error:
                results[name] = {'error': str(error)}
            (args.directory / 'report.json').write_text(json.dumps({
                'revision': args.revision, 'workflows': results}, indent=2) + '\n')
            print(name + ': ' + ('ERROR ' + results[name]['error'] if 'error' in results[name]
                                else str(len(results[name]['children'])) + ' Bazel invocations'), flush=True)
    if any('error' in result for result in results.values()):
        raise RuntimeError('Some BuildBuddy profiles could not be collected; see report.json')


if __name__ == '__main__':
    main()
