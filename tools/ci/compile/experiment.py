"""Compare one real Blink compile with and without Bazel include scanning."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.parse import unquote, urlparse
import uuid


ROOT = Path(__file__).resolve().parents[3]
TARGET = '//tools/ci/compile:blink-layout-linux-amd64'
OWNER = ':blink_layout_compile_probe'


def compile_spawns(path):
    text = path.read_text()
    decoder = json.JSONDecoder()
    offset = 0
    results = []
    while offset < len(text):
        while offset < len(text) and text[offset].isspace():
            offset += 1
        if offset == len(text):
            break
        spawn, offset = decoder.raw_decode(text, offset)
        if spawn.get('mnemonic') == 'CppCompile' and spawn.get('targetLabel', '').endswith(OWNER):
            results.append({
                'input_entries': len(spawn.get('inputs', [])),
                'header_inputs': sum(item.get('path', '').endswith(('.h', '.hpp', '.inc'))
                                     for item in spawn.get('inputs', [])),
                'runner': spawn.get('runner'),
                'cache_hit': spawn.get('cacheHit', False),
                'metrics': spawn.get('metrics', {}),
            })
    if len(results) != 1:
        raise ValueError('Expected exactly one Blink compiler spawn, got ' + str(len(results)))
    return results[0]


def archive_outputs(events):
    sets, roots = {}, []
    complete = False
    metrics = {}
    for line in events.read_text().splitlines():
        event = json.loads(line)
        if 'namedSetOfFiles' in event:
            sets[event['id']['namedSet']['id']] = event['namedSetOfFiles']
        if event.get('id', {}).get('targetCompleted', {}).get('label') == TARGET:
            complete = event['completed']['success']
            for group in event['completed'].get('outputGroup', []):
                if group['name'] == 'default':
                    roots += [item['id'] for item in group.get('fileSets', [])]
        if 'buildMetrics' in event:
            metrics = event['buildMetrics']
    if not complete:
        raise ValueError('Blink compile target did not complete')
    files, visited = set(), set()
    while roots:
        identifier = roots.pop()
        if identifier in visited:
            continue
        visited.add(identifier)
        group = sets[identifier]
        roots += [item['id'] for item in group.get('fileSets', [])]
        for item in group.get('files', []):
            uri = urlparse(item['uri'])
            if uri.scheme != 'file' or uri.netloc:
                raise ValueError('Compiler outputs must be downloaded locally')
            file = Path(unquote(uri.path))
            if file.suffix == '.a':
                files.add(file)
    if not files:
        raise ValueError('Blink compile did not produce an archive')
    digests = {}
    for file in sorted(files):
        with file.open('rb') as source:
            digests[file.name] = hashlib.file_digest(source, 'sha256').hexdigest()
    return digests, metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    if not os.environ.get('BUILDBUDDY_CI_RUNNER_ABSPATH'):
        raise ValueError('Compile experiment requires a BuildBuddy workflow runner')
    args.directory.mkdir(parents=True, exist_ok=True)
    nonce = uuid.uuid4().hex
    report = {}
    with tempfile.TemporaryDirectory(prefix='blink-compile-profile-') as temporary:
        for mode in ('baseline', 'include-scan'):
            events, spawns = Path(temporary) / 'events.json', Path(temporary) / 'spawns.json'
            command = [os.environ.get('BAZEL', 'bazel'), 'build', '--config=browser', '--config=buildbuddy',
                       '--per_file_copt=.*layout_box.cc@-DBAZEL_COMPILE_PROFILE_RUN=' + nonce,
                       '--build_event_json_file=' + str(events),
                       '--nobuild_event_json_file_path_conversion',
                       '--execution_log_json_file=' + str(spawns),
                       '--noexecution_log_sort',
                       '--cc_include_scanning=' + ('true' if mode == 'include-scan' else 'false'), TARGET]
            result = subprocess.run(command, cwd=ROOT)
            if result.returncode:
                report[mode] = {'exit_code': result.returncode}
                (args.directory / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
                raise RuntimeError(mode + ' compile failed')
            digests, metrics = archive_outputs(events)
            report[mode] = dict(compile_spawns(spawns), output_sha256=digests, build_metrics=metrics)
            (args.directory / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
            print(mode + ': ' + str(report[mode]['input_entries']) + ' compiler inputs', flush=True)
    if report['baseline']['output_sha256'] != report['include-scan']['output_sha256']:
        raise ValueError('Include scanning changed compiler output bytes')
    print('Compiler output bytes match', flush=True)


if __name__ == '__main__':
    main()
