#!/usr/bin/env python3
"""Regenerate platform base and support metadata in an isolated overlay."""

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CXX = 'third_party/rust/chromium_crates_io/vendor/cxx-v1'


def atomic_copy(source, target):
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as output:
        temporary = Path(output.name)
    try:
        shutil.copy2(source, temporary)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant', required=True, choices=['windows_amd64', 'windows_arm64', 'darwin_arm64'])
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--output', type=Path, help='Write metadata to this directory instead of the maintained profile')
    parser.add_argument('--ipc', action='store_true', help='Also import Mojo runtime, bindings and URL traits')
    parser.add_argument('--network', action='store_true', help='Also import the network closure and its support libraries')
    args = parser.parse_args()
    args.ipc = args.ipc or args.network
    source = args.source_root.resolve()
    graph = ROOT / 'native' / (args.variant + '.json.gz')
    destination = args.output or ROOT / 'platforms' / args.variant / 'overlay'
    with tempfile.TemporaryDirectory(prefix='chromium-platform-import-') as temporary:
        stage = Path(temporary) / 'chromium'
        overlay = stage / 'bcr/overlay'
        shutil.copytree(ROOT / 'tools', stage / 'tools', ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copy2(ROOT / 'MODULE.bazel', stage / 'MODULE.bazel')
        (stage / 'native').mkdir()
        for path in (ROOT / 'bcr/overlay').rglob('BUILD.bazel'):
            target = overlay / path.relative_to(ROOT / 'bcr/overlay')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        commands = [
            ['import_base.py', str(graph), '--source-root', str(source)],
            ['import_generated_files.py', str(graph)],
            ['import_buildflags.py', str(graph)],
            ['import_perfetto_proto.py', str(graph)],
            ['import_perfetto_runtime.py', str(graph), str(source / 'third_party/perfetto')],
            ['import_rust_crates.py', str(graph), '--source-root', str(source),
             '--root', 'rust_logger', '--root', 'serde_json_wrapper', '--root', 'cxxbridge'],
        ]
        if args.variant == 'darwin_arm64' or args.network:
            commands.append(['import_crypto.py', str(graph), '--source-root', str(source)])
        if args.ipc:
            commands.extend([
                ['import_mojo_runtime.py', str(graph), '--source-root', str(source)],
                ['import_mojo_actions.py', str(graph), str(source)],
                ['import_url.py', str(graph), '--source-root', str(source)],
            ])
        if args.network:
            commands.extend([
                ['import_sqlite.py', str(graph)],
                ['import_quiche.py', str(graph), '--source-root', str(source)],
                ['import_grit_actions.py', str(graph), '--source-root', str(source), '--root', '//net:net_resources_grit'],
                ['import_cpp_layer.py', str(graph), '--source-root', str(source), '--layer', 'network'],
            ])
        for command in commands:
            subprocess.run([sys.executable, str(stage / 'tools' / command[0]), *command[1:]], check=True)
        files = [
            'BUILD.bazel', 'build/BUILD.bazel', 'native/base_sources.bzl',
            'native/generated_files.bzl', 'native/buildflags.bzl',
            'native/perfetto_proto.bzl', 'native/perfetto_proto_targets.json',
            'native/perfetto_runtime.bzl', 'native/rust/crates.bzl', CXX + '/BUILD.bazel',
        ]
        if args.variant == 'darwin_arm64' or args.network:
            files.append('native/crypto_sources.bzl')
        if args.ipc:
            files.append('native/url_sources.bzl')
            files.extend(str(path.relative_to(overlay)) for path in
                         sorted((overlay / 'native').glob('mojo_*.bzl')))
        if args.network:
            files.extend(['native/' + name + '_sources.bzl' for name in ['sqlite', 'quiche', 'network']])
            files.extend(['native/grit_actions.bzl', 'native/grit_sources.bzl', 'native/grit_targets.json'])
            files.extend(str(path.relative_to(overlay)) for path in
                         sorted((overlay / 'native/network_forwarders').rglob('*')) if path.is_file())
        if args.variant.startswith('windows_'):
            build = overlay / 'build/BUILD.bazel'
            build.write_text(build.read_text() + '\nexports_files(["precompile.h"])\n')
        for name in files:
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            atomic_copy(overlay / name, target)
    print('Regenerated ' + args.variant + '; platform rule adapters preserved')


if __name__ == '__main__':
    main()
