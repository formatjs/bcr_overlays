#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Bundle the combined source extension for a standalone Chromium module."""

import argparse
import ast
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

if __package__:
    from .stage_bcr_entry import stage_entry
else:
    from stage_bcr_entry import stage_entry


PREFIX = 'native/support'


def module_template(workspace, version, versions):
    text = (workspace/'MODULE.bazel').read_text()
    statements = []
    for node in ast.parse(text).body:
        call = node.value if isinstance(node, (ast.Expr, ast.Assign)) else None
        function = call.func.id if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) else None
        if function == 'module':
            statements.append('module(name = "chromium", version = ' + json.dumps(version)
                              + ', bazel_compatibility = [">=9.2.0"])')
            continue
        if function in ['archive_override', 'single_version_override', 'register_toolchains']:
            continue
        if function == 'bazel_dep':
            keywords = {item.arg: item for item in call.keywords}
            name = ast.literal_eval(keywords['name'].value)
            if name in versions:
                keywords['version'].value = ast.Constant(versions[name])
            statements.append(ast.unparse(call))
            continue
        if (function == 'use_repo' and isinstance(call.args[0], ast.Name)
                and call.args[0].id == 'sources'):
            call.args = [arg for arg in call.args
                         if not isinstance(arg, ast.Constant) or arg.value != 'chromium']
            statements.append(ast.unparse(call))
            continue
        statements.append(ast.get_source_segment(text, node))
    module = '\n\n'.join(statements) + '\n'
    module = module.replace('//build:', '//' + PREFIX + '/build:')
    return module.replace('//overlays/chromium/bcr/overlay/native', '//native')


def support_files(workspace):
    text = (workspace/'build/dependencies.bzl').read_text()
    declaration = next(node for node in ast.parse(text).body
                       if isinstance(node, ast.Assign) and node.targets[0].id == '_OVERLAYS')
    overlays = [name for name in ast.literal_eval(declaration.value) if name != 'chromium']
    lines = text.splitlines(keepends=True)
    lines[declaration.lineno - 1:declaration.end_lineno] = [
        '_OVERLAYS = ' + json.dumps(overlays, indent=4) + '\n']
    files = {}

    def collect(source, relative):
        if source.is_symlink():
            raise ValueError('symlink in bundled support: ' + str(source))
        if source.is_dir():
            for child in sorted(source.iterdir()):
                if child.name == '__pycache__' or child.name.startswith('bazel-'):
                    continue
                collect(child, relative/child.name)
        elif source.is_file():
            files[relative.as_posix()] = source.read_bytes()

    collect(workspace/'build', Path('build'))
    for name in overlays:
        collect(workspace/'overlays'/name/'bcr', Path('overlays')/name/'bcr')
    files['build/dependencies.bzl'] = ''.join(lines).encode()
    for path, data in list(files.items()):
        if path.startswith('build/') and path.endswith('.bzl'):
            text = data.decode().replace('"//build:', '"//' + PREFIX + '/build:')
            text = text.replace('"//:overlays.json"', '"//' + PREFIX + ':overlays.json"')
            text = text.replace('"//overlays/chromium:', '"//' + PREFIX + '/overlays/chromium:')
            files[path] = text.encode()
    files['overlays.json'] = (workspace/'overlays.json').read_bytes()
    for relative in ['native/platform_runtime.json', 'bcr/overlay/native/quiche_repository.BUILD.bazel']:
        files['overlays/chromium/' + relative] = (workspace/'overlays/chromium'/relative).read_bytes()
    files['BUILD.bazel'] = b'exports_files(["overlays.json"])\n'
    files['overlays/chromium/BUILD.bazel'] = b'exports_files(["native/platform_runtime.json"])\n'
    return {PREFIX + '/' + path: data for path, data in files.items()}


def write_support(files, destination):
    if destination.exists():
        raise ValueError('support destination already exists: ' + str(destination))
    for relative, data in files.items():
        path = destination/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    manifest = {path: hashlib.sha256(data).hexdigest() for path, data in sorted(files.items())}
    (destination/'support_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


def registry_versions(workspace):
    versions = {}
    for metadata in (workspace/'compatibility_registry/modules').glob('*/metadata.json'):
        versions[metadata.parent.name] = json.loads(metadata.read_text())['versions'][-1]
    for name in ['abseil-cpp', 'boringssl']:
        metadata = workspace/'overlays'/name/'bcr/metadata.json'
        versions[name] = json.loads(metadata.read_text())['versions'][-1]
    return versions


def stage_chromium(workspace, target_registry, version):
    """Stage the browser overlay with its private source repositories bundled."""
    files = support_files(workspace)
    module = module_template(workspace, '', registry_versions(workspace))
    registry = workspace/'overlays/chromium/bcr'
    for path in [registry, *registry.rglob('*')]:
        if path.is_symlink():
            raise ValueError('symlink in published source: ' + str(path))
    consumer = {}
    for name in ['MODULE.bazel', 'BUILD.bazel', '.bazelrc', '.bazelversion']:
        path = workspace/'overlays/chromium/tests/browser_bcr'/name
        if path.is_symlink():
            raise ValueError('symlink in published source: ' + str(path))
        consumer[name] = path.read_bytes()
    with tempfile.TemporaryDirectory(prefix='chromium-module-') as temporary:
        source = Path(temporary)/'bcr'
        shutil.copytree(registry, source, symlinks=True)
        for relative, data in files.items():
            destination = source/'overlay'/relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        (source/'MODULE.bazel').write_text(module)
        (source/'overlay/MODULE.bazel').write_text(module)
        (source/'overlay/browser_bcr').mkdir()
        for name, data in consumer.items():
            (source/'overlay/browser_bcr'/name).write_bytes(data)
        (source/'presubmit.yml').write_text(json.dumps({
            'bcr_test_module': {
                'module_path': 'browser_bcr',
                'tasks': {'browser': {
                    'name': 'Chromium native browser bundle',
                    'platform': 'ubuntu2404', 'bazel': '9.2.0',
                    'build_targets': ['//:browser'],
                }},
            },
        }, indent=2) + '\n')
        return stage_entry(source, target_registry, 'chromium', version)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=Path(__file__).resolve().parents[1])
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument('--destination', type=Path)
    output.add_argument('--target-registry', type=Path)
    parser.add_argument('--version', default='142.0.7444.59')
    args = parser.parse_args()
    if args.target_registry is not None:
        staged = stage_chromium(args.workspace, args.target_registry, args.version)
        print(f'Staged standalone chromium@{args.version} at {staged}')
        return
    files = support_files(args.workspace)
    write_support(files, args.destination)
    (args.destination/'MODULE.bazel').write_text(
        module_template(args.workspace, args.version, registry_versions(args.workspace)))
    print(f'Bundled {len(files)} source-support files ({sum(map(len, files.values()))} bytes)')


if __name__ == '__main__':
    main()
