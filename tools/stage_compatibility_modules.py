#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Stage root compatibility overrides together as versioned registry entries."""

import argparse
import ast
import base64
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import urllib.parse
import urllib.request

if __package__:
    from .check_compatibility_modules import consumer_cases
    from .stage_bcr_entry import require_maintainers, require_repository_url
else:
    from check_compatibility_modules import consumer_cases
    from stage_bcr_entry import require_maintainers, require_repository_url


def integrity(data):
    return 'sha256-' + base64.b64encode(hashlib.sha256(data).digest()).decode()


def relative_path(value):
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise ValueError(f'invalid registry path: {value}')
    return path.as_posix()


def registry_url(registry, relative):
    if not urllib.parse.urlparse(registry).scheme:
        registry = Path(registry).resolve().as_uri()
    return registry.rstrip('/') + '/' + relative


def read_registry(registry, relative, hashes=None):
    url = registry_url(registry, relative)
    if hashes is not None and url not in hashes:
        raise ValueError(f'registry file missing from module lock: {url}')
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read()
    if hashes is not None and hashlib.sha256(data).hexdigest() != hashes[url]:
        raise ValueError(f'registry integrity mismatch: {url}')
    return data


def definitions(module_file):
    dependencies, overrides = {}, {}
    for node in ast.parse(module_file.read_text()).body:
        if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
            continue
        call = node.value
        if not isinstance(call.func, ast.Name):
            continue
        kind = call.func.id
        if kind not in ('bazel_dep', 'archive_override', 'single_version_override'):
            continue
        values = {key.arg: ast.literal_eval(key.value) for key in call.keywords}
        if kind == 'bazel_dep':
            dependencies[values['name']] = values['version']
        else:
            overrides[values['module_name']] = dict(values, kind=kind)
    return dependencies, overrides


def patch_paths(data, strip):
    # Ask Git to parse hunk boundaries and quoted paths; never apply the patch.
    if not data.endswith(b'\n'):
        data += b'\n'
    result = subprocess.run(
        ['git', 'apply', '--numstat', '--recount', '-z', f'-p{strip}', '-'],
        input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    paths = []
    for record in result.stdout.split(b'\0'):
        if not record:
            continue
        parts = record.split(b'\t', 2)
        if len(parts) != 3 or not parts[2]:
            raise ValueError('patch renames are not supported')
        paths.append(relative_path(parts[2].decode()))
    return paths


def stamp_module(text, name, version):
    calls = [node.value for node in ast.parse(text).body
             if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
             and isinstance(node.value.func, ast.Name) and node.value.func.id == 'module']
    if len(calls) != 1:
        raise ValueError('expected one module declaration')
    keywords = {key.arg: key.value for key in calls[0].keywords}
    if ast.literal_eval(keywords['name']) != name:
        raise ValueError(f'resolved repository has wrong module name: {name}')
    value = keywords['version']
    lines = text.encode().splitlines(keepends=True)
    start = sum(map(len, lines[:value.lineno - 1])) + value.col_offset
    end = sum(map(len, lines[:value.end_lineno - 1])) + value.end_col_offset
    return (text.encode()[:start] + json.dumps(version).encode() + text.encode()[end:]).decode()


def rewrite_dependencies(text, versions):
    replacements = []
    lines = text.encode().splitlines(keepends=True)
    for node in ast.parse(text).body:
        if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
            continue
        call = node.value
        if not isinstance(call.func, ast.Name) or call.func.id != 'bazel_dep':
            continue
        keywords = {key.arg: key.value for key in call.keywords}
        if 'dev_dependency' in keywords and ast.literal_eval(keywords['dev_dependency']):
            continue
        name = ast.literal_eval(keywords['name'])
        if name not in versions or 'version' not in keywords:
            continue
        value = keywords['version']
        start = sum(map(len, lines[:value.lineno - 1])) + value.col_offset
        end = sum(map(len, lines[:value.end_lineno - 1])) + value.end_col_offset
        replacements.append((start, end, json.dumps(versions[name]).encode()))
    data = text.encode()
    for start, end, value in sorted(replacements, reverse=True):
        data = data[:start] + value + data[end:]
    return data.decode()


def selected_versions(external):
    versions = {}
    for repository in external.glob('*+'):
        path = repository / 'MODULE.bazel'
        if not path.is_file():
            continue
        for node in ast.parse(path.read_text()).body:
            if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Name) and node.value.func.id == 'module'):
                values = {key.arg: key.value for key in node.value.keywords}
                name = ast.literal_eval(values['name'])
                version = ast.literal_eval(values['version'])
                if version:
                    versions[name] = version
    return versions


def local_patch(workspace, label):
    if not label.startswith('//') or ':' not in label:
        raise ValueError(f'expected workspace patch label: {label}')
    package, filename = label[2:].split(':', 1)
    relative = relative_path('/'.join(part for part in [package, filename] if part))
    path = (workspace / relative).resolve()
    if not path.is_relative_to(workspace.resolve()):
        raise ValueError(f'patch escapes workspace: {label}')
    return path


def prepare_entry(workspace, external, registry, hashes, name, base, override, suffix,
                  dependency_versions=None):
    version = base + '.' + suffix
    if not re.fullmatch(r'[a-z][a-z0-9._-]*', name) or not re.fullmatch(
            r'[A-Za-z0-9][A-Za-z0-9._+-]*', version):
        raise ValueError(f'invalid module or version: {name}@{version}')
    source_prefix = f'modules/{name}/{base}/'
    paths = {'MODULE.bazel'}
    provenance = {'base_module': name + '@' + base, 'patches': {}}
    if override['kind'] == 'archive_override':
        urls = override['urls']
        source = {'url': urls[0], 'integrity': override['integrity']}
        if len(urls) > 1:
            source['mirror_urls'] = urls[1:]
        if 'strip_prefix' in override:
            source['strip_prefix'] = override['strip_prefix']
    else:
        data = read_registry(registry, source_prefix + 'source.json', hashes)
        source = json.loads(data)
        provenance['upstream_source_sha256'] = hashlib.sha256(data).hexdigest()
        paths.update(relative_path(path) for path in source.get('overlay', {}))
        for path, expected in source.get('patches', {}).items():
            data = read_registry(registry, source_prefix + 'patches/' + relative_path(path))
            if integrity(data) != expected:
                raise ValueError(f'upstream patch integrity mismatch: {name}/{path}')
            paths.update(patch_paths(data, source.get('patch_strip', 0)))
    for label in override.get('patches', []):
        path = local_patch(workspace, label)
        data = path.read_bytes()
        paths.update(patch_paths(data, override.get('patch_strip', 0)))
        provenance['patches'][label] = integrity(data)
    repository = (external / (name + '+')).resolve()
    overlay = {}
    for relative in sorted(paths):
        path = (repository / relative).resolve()
        if not path.is_relative_to(repository) or not path.is_file():
            raise ValueError(f'cannot snapshot removed or missing file: {name}/{relative}')
        if path.stat().st_mode & 0o111 and relative not in source.get('overlay', {}):
            raise ValueError(f'cannot overlay executable change: {name}/{relative}')
        overlay[relative] = path.read_bytes()
    module = stamp_module(overlay['MODULE.bazel'].decode(), name, version)
    overlay['MODULE.bazel'] = module.encode()
    for path, data in overlay.items():
        if path.endswith('MODULE.bazel'):
            overlay[path] = rewrite_dependencies(data.decode(), dependency_versions or {}).encode()
    module = overlay['MODULE.bazel'].decode()
    dependencies = set()
    for node in ast.parse(module).body:
        if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name) and node.value.func.id == 'bazel_dep'):
            values = {key.arg: ast.literal_eval(key.value) for key in node.value.keywords}
            if not values.get('dev_dependency'):
                dependencies.add(values['name'])
    if dependencies & {'nasm', 'rules_nasm'} and 'rules_cc_autoconf' not in dependencies:
        # NASM's older checker misses <iterator> with hermetic LLVM.
        version_floor = (dependency_versions or {}).get('rules_cc_autoconf')
        if not version_floor:
            raise ValueError('missing tested rules_cc_autoconf version for NASM')
        module += '\nbazel_dep(name = "rules_cc_autoconf", version = ' + json.dumps(version_floor) + ')\n'
        overlay['MODULE.bazel'] = module.encode()
        provenance['added_dependencies'] = {'rules_cc_autoconf': version_floor}
    # Publish the effective files once; do not replay upstream patches over them.
    source.pop('patch_strip', None)
    source['patches'] = {}
    source['overlay'] = {path: integrity(data) for path, data in overlay.items()}
    metadata = json.loads(read_registry(registry, f'modules/{name}/metadata.json'))
    metadata.update(versions=[version], yanked_versions={})
    return dict(name=name, version=version, source=source, overlay=overlay,
                module=module, metadata=metadata, provenance=provenance)


def add_presubmit(entry, consumer, source):
    if any(label[1:].split('//')[0] != entry['name'] for label in consumer['targets']):
        raise ValueError('consumer targets must belong to the staged module')
    files = {
        'MODULE.bazel': rewrite_dependencies(consumer['module'], {entry['name']: entry['version']}),
        'BUILD.bazel': 'filegroup(\n    name = "libraries",\n    srcs = ' + json.dumps(consumer['targets']) + ',\n)\n',
        '.bazelrc': (source/'.bazelrc').read_text(),
        '.bazelversion': (source/'.bazelversion').read_text(),
    }
    task = dict(name='Native ' + entry['name'] + ' with hermetic LLVM',
                platform='ubuntu2404', bazel='${{ bazel }}', build_targets=['//:libraries'])
    if entry['name'] == 'cpuinfo':
        files['cpuinfo_consumer_test.cc'] = (source/'cpuinfo_consumer_test.cc').read_text()
        files['BUILD.bazel'] = ('load("@rules_cc//cc:cc_test.bzl", "cc_test")\n\n'
                               + files['BUILD.bazel'] + '\ncc_test(\n'
                               '    name = "cpuinfo_consumer_test",\n'
                               '    srcs = ["cpuinfo_consumer_test.cc"],\n'
                               '    deps = ["@cpuinfo"],\n)\n')
        task['test_targets'] = ['//:cpuinfo_consumer_test']
    for name, text in files.items():
        path = 'bcr_test/' + name
        if path in entry['overlay']:
            raise ValueError('consumer overlay already exists: ' + path)
        entry['overlay'][path] = text.encode()
        entry['source']['overlay'][path] = integrity(text.encode())
    entry['presubmit'] = {'bcr_test_module': {
        'module_path': 'bcr_test',
        'matrix': {'bazel': [files['.bazelversion'].strip()]},
        'tasks': {'linux': task},
    }}


def stage_entries(entries, destination):
    for entry in entries:
        require_maintainers(entry['metadata'])
        require_repository_url(entry['metadata'], entry['source'])
        module = destination / 'modules' / entry['name']
        if (module / entry['version']).exists() or (module / 'metadata.json').exists():
            raise ValueError(f'target module already exists: {entry["name"]}')
    destination.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        module = destination / 'modules' / entry['name']
        module.mkdir(parents=True)
        target = module / entry['version']
        target.mkdir()
        for relative, data in entry['overlay'].items():
            path = target / 'overlay' / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (target / 'MODULE.bazel').write_text(entry['module'])
        if entry.get('presubmit'):
            (target / 'presubmit.yml').write_text(json.dumps(entry['presubmit'], indent=2) + '\n')
        for filename, value in [('source.json', entry['source']),
                                ('provenance.json', entry['provenance'])]:
            (target / filename).write_text(json.dumps(value, indent=4) + '\n')
        (module / 'metadata.json').write_text(json.dumps(entry['metadata'], indent=4) + '\n')
    configuration = destination / 'bazel_registry.json'
    if not configuration.exists():
        configuration.write_text('{}\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--module-file', type=Path)
    parser.add_argument('--external-root', type=Path, required=True)
    parser.add_argument('--target-registry', type=Path, required=True)
    parser.add_argument('--registry', default='https://bcr.bazel.build')
    parser.add_argument('--suffix', default='chromium142')
    parser.add_argument('--only', nargs='+')
    args = parser.parse_args()
    dependencies, overrides = definitions(args.module_file or args.workspace / 'MODULE.bazel')
    hashes = json.loads((args.workspace / 'MODULE.bazel.lock').read_text())['registryFileHashes']
    dependency_versions = selected_versions(args.external_root)
    selected = {name: override for name, override in overrides.items()
                if not (args.workspace / 'overlays' / name / 'bcr').is_dir()
                and name != 'libxslt'
                and (not args.only or name in args.only)}
    dependency_versions.update({name: override.get('version', dependencies[name]) + '.' + args.suffix
                                for name, override in selected.items()})
    entries = []
    consumer_source = args.workspace / 'compatibility_registry/tests'
    consumers = consumer_cases(consumer_source)
    for name, override in sorted(selected.items()):
        base = override.get('version', dependencies[name])
        entries.append(prepare_entry(args.workspace, args.external_root, args.registry,
                                     hashes, name, base, override, args.suffix,
                                     dependency_versions))
        add_presubmit(entries[-1], consumers[name], consumer_source)
    if not entries or args.only and set(args.only) != {entry['name'] for entry in entries}:
        raise ValueError('requested compatibility overrides were not found')
    stage_entries(entries, args.target_registry)
    for entry in entries:
        print(f'staged {entry["name"]}@{entry["version"]}: {len(entry["overlay"])} files')


if __name__ == '__main__':
    main()
