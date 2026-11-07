"""Compare real Blink compiles with and without Bazel include scanning."""

import argparse
import gzip
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
TARGETS = {'linux-amd64': TARGET, **{
    platform: '//tools/ci/compile/' + platform.replace('-', '_') + ':blink-layout-' + platform
    for platform in ('linux-arm64', 'darwin-arm64', 'windows-amd64', 'windows-arm64')
}}
OWNERS = (':blink_layout_compile_probe', ':blink_layout_compile_probe_canvas')
SOURCES = ('layout_box.cc', 'layout_view.cc', 'svg_object_painter.cc',
           'css_palette_mix_value.cc', 'css_relative_color_value.cc', 'core_probes.cc')
SOURCE_PATTERN = '.*(' + '|'.join(source.removesuffix('.cc') for source in SOURCES) + ')[.]cc'


def compiler_input_diff(path):
    changes = [item for item in json.loads(path.read_text()).get('spawn_diffs', [])
               if item.get('mnemonic') == 'CppCompile' and item.get('target_label', '').endswith(OWNERS)]
    if any('old_only' in item or 'new_only' in item for item in changes):
        return {'comparison': 'unpaired', 'reason': 'Compiler output paths changed between configurations'}
    removed, added = 0, 0
    for item in changes:
        for difference in item.get('modified', {}).get('diffs', []):
            paths = difference.get('input_paths', {})
            removed += len(paths.get('old_only', []))
            added += len(paths.get('new_only', []))
    return {'comparison': 'paired', 'input_paths_removed': removed, 'input_paths_added': added}


def compiler_profile(path, source_name='layout_box.cc'):
    with gzip.open(path, 'rt') as source:
        events = [event for event in json.load(source)['traceEvents']
                  if event.get('ph') == 'X' and event.get('dur', 0) > 0]
    compiles = [event for event in events if event.get('cat') == 'action processing'
                and event.get('name', '').startswith('Compiling ') and source_name in event['name']]
    if len(compiles) != 1:
        raise ValueError('Expected exactly one Blink compiler timing span')
    compile_event = compiles[0]
    nested = [event for event in events if event.get('tid') == compile_event['tid']
              and event['ts'] >= compile_event['ts']
              and event['ts'] + event['dur'] <= compile_event['ts'] + compile_event['dur'] + 1000]
    return {
        'action_seconds': compile_event['dur'] / 1e6,
        'worker_seconds': sum(event['dur'] for event in nested
                              if event.get('cat') == 'Remote execution process wall time') / 1e6,
        'merkle_seconds': sum(event['dur'] for event in nested
                              if event.get('name') == 'MerkleTreeComputer.buildForSpawn') / 1e6,
    }


def archive_outputs(events, target=TARGET):
    sets, roots = {}, []
    complete = False
    metrics = {}
    for line in events.read_text().splitlines():
        event = json.loads(line)
        if 'namedSetOfFiles' in event:
            sets[event['id']['namedSet']['id']] = event['namedSetOfFiles']
        if event.get('id', {}).get('targetCompleted', {}).get('label') == target:
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
            if file.suffix in ('.a', '.lib'):
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
    parser.add_argument('--platform', choices=sorted(TARGETS), default='linux-amd64')
    args = parser.parse_args()
    if not os.environ.get('BUILDBUDDY_CI_RUNNER_ABSPATH'):
        raise ValueError('Compile experiment requires a BuildBuddy workflow runner')
    args.directory.mkdir(parents=True, exist_ok=True)
    nonce = uuid.uuid4().hex
    report = {}
    with tempfile.TemporaryDirectory(prefix='blink-compile-profile-') as temporary:
        for mode in ('baseline-1', 'include-scan-1', 'include-scan-2', 'baseline-2'):
            events = Path(temporary) / 'events.json'
            execution_log = Path(temporary) / (mode + '.binpb.zst')
            profile = Path(temporary) / (mode + '.profile.gz')
            command = [os.environ.get('BAZEL', 'bazel'), 'build', '--config=browser', '--config=buildbuddy',
                       '--per_file_copt=' + SOURCE_PATTERN + '@-DBAZEL_COMPILE_PROFILE_RUN=' + nonce + '_' + mode.replace('-', '_'),
                       '--build_event_json_file=' + str(events),
                       '--nobuild_event_json_file_path_conversion',
                       '--execution_log_compact_file=' + str(execution_log),
                       '--profile=' + str(profile),
                       '--cc_include_scanning=' + ('true' if mode.startswith('include-scan') else 'false')]
            if args.platform.startswith('windows-'):
                command.extend([
                    '--repo_env=BAZEL_MSVC_RUNTIME_VISUAL_STUDIO_EULA=1',
                    '--repo_env=BAZEL_WINDOWS_SDK_EULA=1',
                ])
            command.append(TARGETS[args.platform])
            result = subprocess.run(command, cwd=ROOT)
            if result.returncode:
                report[mode] = {'exit_code': result.returncode}
                (args.directory / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
                raise RuntimeError(mode + ' compile failed')
            digests, metrics = archive_outputs(events, TARGETS[args.platform])
            report[mode] = {
                'compiles': {source: compiler_profile(profile, source) for source in SOURCES},
                'output_sha256': digests,
                'build_metrics': metrics,
            }
            (args.directory / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
            print(mode + ': ' + json.dumps(report[mode]['compiles']), flush=True)
        report['output_bytes_match'] = all(
            result['output_sha256'] == report['baseline-1']['output_sha256']
            for result in report.values())
        (args.directory / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        if not report['output_bytes_match']:
            raise ValueError('Include scanning changed compiler output bytes')
        report['input_diff'] = {}
        for pair in ('1', '2'):
            diff = Path(temporary) / ('diff-' + pair + '.json')
            with diff.open('w') as output:
                subprocess.run(['bb', 'explain', '--old', str(Path(temporary) / ('baseline-' + pair + '.binpb.zst')),
                                '--new', str(Path(temporary) / ('include-scan-' + pair + '.binpb.zst')),
                                '--output_format', 'json'], stdout=output, cwd=ROOT, check=True)
            report['input_diff'][pair] = compiler_input_diff(diff)
        (args.directory / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Compiler output bytes match', flush=True)


if __name__ == '__main__':
    main()
