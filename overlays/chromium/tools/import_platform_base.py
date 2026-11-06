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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant', required=True, choices=['windows_amd64', 'windows_arm64', 'darwin_arm64'])
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--output', type=Path, help='Write metadata to this directory instead of the maintained profile')
    args = parser.parse_args()
    source = args.source_root.resolve()
    graph = ROOT / 'native' / (args.variant + '.json.gz')
    destination = args.output or ROOT / 'platforms' / args.variant / 'overlay'
    with tempfile.TemporaryDirectory(prefix='chromium-platform-import-') as temporary:
        stage = Path(temporary) / 'chromium'
        overlay = stage / 'bcr/overlay'
        shutil.copytree(ROOT / 'tools', stage / 'tools', ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copy2(ROOT / 'MODULE.bazel', stage / 'MODULE.bazel')
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
        if args.variant == 'darwin_arm64':
            commands.append(['import_crypto.py', str(graph), '--source-root', str(source)])
        for command in commands:
            subprocess.run([sys.executable, str(stage / 'tools' / command[0]), *command[1:]], check=True)
        files = [
            'BUILD.bazel', 'build/BUILD.bazel', 'native/base_sources.bzl',
            'native/generated_files.bzl', 'native/buildflags.bzl',
            'native/perfetto_proto.bzl', 'native/perfetto_proto_targets.json',
            'native/perfetto_runtime.bzl', 'native/rust/crates.bzl', CXX + '/BUILD.bazel',
        ]
        if args.variant == 'darwin_arm64':
            files.append('native/crypto_sources.bzl')
        for name in files:
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(overlay / name, target)
        if args.variant.startswith('windows_'):
            build = destination / 'build/BUILD.bazel'
            build.write_text(build.read_text() + '\nexports_files(["precompile.h"])\n')
    print('Regenerated ' + args.variant + '; platform rule adapters preserved')


if __name__ == '__main__':
    main()
