"""Compare real Blink compiles with and without Bazel include scanning."""

import argparse
import ast
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.parse import unquote, urlparse
import uuid

from tools.ci.profile_buildbuddy import trace_summary


ROOT = Path(__file__).resolve().parents[3]
TARGET = '//tools/ci/compile:blink-layout-linux-amd64'
TARGETS = {'linux-amd64': TARGET, **{
    platform: '//tools/ci/compile/' + platform.replace('-', '_') + ':blink-layout-' + platform
    for platform in ('linux-arm64', 'darwin-arm64', 'windows-amd64', 'windows-arm64')
}}
OWNERS = tuple(':blink_layout_compile_probe' + suffix for suffix in (
    '', '_canvas', '_accessibility', '_canvas2d', '_platform', '_bindings',
    '_graphics', '_mediastream', '_webcodecs'))
SOURCES = ('layout_box.cc', 'layout_view.cc', 'svg_object_painter.cc',
           'css_palette_mix_value.cc', 'css_relative_color_value.cc', 'core_probes.cc')
WIDE_HOST_SOURCES = (*SOURCES, 'ax_object.cc', 'ax_node_object.cc', 'canvas_rendering_context_2d.cc',
                     'date_math.cc', 'v8_video_frame.cc', 'v8_webgl2_rendering_context_webgpu.cc',
                     'html_permission_element_strings_map.cc',
                     'accelerated_static_bitmap_image.cc', 'mailbox_texture_backing.cc', 'video_frame_image_util.cc',
                     'convert_to_webrtc_video_frame_buffer.cc', 'web_media_player_ms_compositor.cc', 'video_frame.cc')


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


def compiler_profiles(path, sources):
    with gzip.open(path, 'rt') as source:
        events = [event for event in json.load(source)['traceEvents']
                  if event.get('ph') == 'X' and event.get('dur', 0) > 0]
    compile_events = [(event['name'].removeprefix('Compiling ').removesuffix(' [for tool]'), event)
                      for event in events if event.get('cat') == 'action processing'
                      and event.get('name', '').startswith('Compiling ')]
    results = {}
    for source_name in sources:
        compiles = [event for compiled, event in compile_events
                    if compiled == source_name or compiled.endswith('/' + source_name)]
        if len(compiles) != 1:
            raise ValueError('Expected exactly one Blink compiler timing span: ' + source_name)
        compile_event = compiles[0]
        nested = [event for event in events if event.get('tid') == compile_event['tid']
                  and event['ts'] >= compile_event['ts']
                  and event['ts'] + event['dur'] <= compile_event['ts'] + compile_event['dur'] + 1000]
        # Remote timestamps may extend slightly past the client action interval.
        workers = [event for event in events
                   if event.get('tid') == compile_event['tid']
                   and event.get('cat') == 'Remote execution process wall time'
                   and min(event['ts'] + event['dur'], compile_event['ts'] + compile_event['dur'])
                   - max(event['ts'], compile_event['ts']) > event['dur'] / 2]
        results[source_name] = {
            'action_seconds': compile_event['dur'] / 1e6,
            'worker_seconds': sum(event['dur'] for event in workers) / 1e6,
            'merkle_seconds': sum(event['dur'] for event in nested
                                  if event.get('name') == 'MerkleTreeComputer.buildForSpawn') / 1e6,
        }
    return results


def compiler_profile(path, source_name='layout_box.cc'):
    return compiler_profiles(path, (source_name,))[source_name]


def batch_sources():
    tree = ast.parse(Path(__file__).with_name('batch_sources.bzl').read_text())
    sources = next(ast.literal_eval(node.value) for node in tree.body
                   if isinstance(node, ast.Assign) and any(
                       isinstance(target, ast.Name) and target.id == 'SOURCES' for target in node.targets))
    return (*sources, 'third_party/blink/renderer/core/probe/core_probes.cc')


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
    parser.add_argument('--batch', action='store_true', help='Measure fixed host throughput batch after warmups')
    parser.add_argument('--host-blink', action='store_true', help='Probe Linux ARM64 captured x64 host Blink libraries')
    parser.add_argument('--wide-host-blink', action='store_true', help='Include host modules, platform, and generated bindings')
    parser.add_argument('--compare-merkle-retention', action='store_true',
                        help='Compare retained input trees on the unscanned batch; compiler options stay fixed')
    args = parser.parse_args()
    if args.batch and args.platform != 'linux-amd64':
        parser.error('Throughput batch currently targets Linux amd64 host compiles')
    if (args.host_blink or args.wide_host_blink) and (args.batch or args.platform != 'linux-amd64'):
        parser.error('Host Blink probe runs on Linux amd64 without --batch')
    if args.compare_merkle_retention and not args.batch:
        parser.error('--compare-merkle-retention requires --batch')
    if not os.environ.get('BUILDBUDDY_CI_RUNNER_ABSPATH'):
        raise ValueError('Compile experiment requires a BuildBuddy workflow runner')
    args.directory.mkdir(parents=True, exist_ok=True)
    nonce = uuid.uuid4().hex
    sources = batch_sources() if args.batch else SOURCES
    if args.wide_host_blink:
        sources = WIDE_HOST_SOURCES
    target = '//tools/ci/compile/throughput:blink-throughput-linux-amd64' if args.batch else TARGETS[args.platform]
    if args.host_blink:
        target = '//tools/ci/compile/host:blink-host-linux-arm64'
    if args.wide_host_blink:
        target = '//tools/ci/compile/host_wide:blink-host-linux-arm64'
    pattern = '.*(' + '|'.join(re.escape(source) for source in sources) + ')'
    variant = 'retain-merkle' if args.compare_merkle_retention else 'include-scan'
    modes = [('baseline-1', False), (variant + '-1', True), (variant + '-2', True), ('baseline-2', False)]
    if args.batch:
        modes = [('warmup-baseline', False), ('warmup-' + variant, True)] + modes
    report = {'source_count': len(sources), 'platform': args.platform,
              'comparison': variant,
              'warmup_modes': [mode for mode, _ in modes if mode.startswith('warmup-')]}
    with tempfile.TemporaryDirectory(prefix='blink-compile-profile-') as temporary:
        for mode, experimental in modes:
            scanning = experimental and not args.compare_merkle_retention
            events = Path(temporary) / 'events.json'
            execution_log = Path(temporary) / (mode + '.binpb.zst')
            profile = Path(temporary) / (mode + '.profile.gz')
            command = [os.environ.get('BAZEL', 'bazel'), 'build', '--config=browser', '--config=buildbuddy',
                       '--per_file_copt=' + pattern + '@-DBAZEL_COMPILE_PROFILE_RUN=' + nonce + '_' + mode.replace('-', '_'),
                       '--build_event_json_file=' + str(events),
                       '--nobuild_event_json_file_path_conversion',
                       '--execution_log_compact_file=' + str(execution_log),
                       '--profile=' + str(profile),
                       '--cc_include_scanning=' + ('true' if scanning else 'false')]
            if args.compare_merkle_retention:
                command.append('--experimental_remote_discard_merkle_trees=' + ('false' if experimental else 'true'))
            if args.platform.startswith('windows-'):
                command.extend([
                    '--repo_env=BAZEL_MSVC_RUNTIME_VISUAL_STUDIO_EULA=1',
                    '--repo_env=BAZEL_WINDOWS_SDK_EULA=1',
                ])
            command.append(target)
            result = subprocess.run(command, cwd=ROOT)
            if result.returncode:
                report[mode] = {'exit_code': result.returncode}
                (args.directory / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
                raise RuntimeError(mode + ' compile failed')
            digests, metrics = archive_outputs(events, target)
            timings = compiler_profiles(profile, sources)
            if any(item['worker_seconds'] <= 0 for item in timings.values()):
                raise ValueError('Expected real remote worker execution for every selected compile')
            report[mode] = {
                'compiles': timings,
                'output_sha256': digests,
                'build_metrics': metrics,
                'profile_summary': trace_summary(profile),
            }
            (args.directory / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
            print(mode + ': ' + (str(len(sources)) + ' compiler spans recorded' if args.batch
                                else json.dumps(report[mode]['compiles'])), flush=True)
        report['output_bytes_match'] = all(
            report[mode]['output_sha256'] == report['baseline-1']['output_sha256']
            for mode, _ in modes)
        (args.directory / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        if not report['output_bytes_match']:
            raise ValueError('Build experiment changed compiler output bytes')
        report['input_diff'] = {}
        for pair in ('1', '2'):
            diff = Path(temporary) / ('diff-' + pair + '.json')
            with diff.open('w') as output:
                subprocess.run(['bb', 'explain', '--old', str(Path(temporary) / ('baseline-' + pair + '.binpb.zst')),
                                '--new', str(Path(temporary) / (variant + '-' + pair + '.binpb.zst')),
                                '--output_format', 'json'], stdout=output, cwd=ROOT, check=True)
            report['input_diff'][pair] = compiler_input_diff(diff)
        (args.directory / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Compiler output bytes match', flush=True)


if __name__ == '__main__':
    main()
