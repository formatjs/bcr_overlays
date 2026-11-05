#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Import complete supported WebUI preprocessing/TypeScript/bundling closures."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

from import_base import replace_block, sort_archive_files

ROOT = Path(__file__).resolve().parents[1]
BUILD = '//out/bazel-import/'
NODE = '//third_party/node/linux/node-linux-x64/bin/node'
PERMISSION_GENERATOR = '//third_party/blink/renderer/build/scripts/generate_permission_element_grd.py'
SUPPORTED = {
    '//tools/grit/preprocess_if_expr.py', '//ui/webui/resources/tools/generate_grd.py',
    '//tools/typescript/ts_library.py', '//tools/typescript/path_mappings.py',
    '//ui/webui/resources/tools/minify_js.py', '//ui/webui/resources/tools/bundle_js.py',
    '//ui/webui/resources/tools/eslint_ts.py', '//tools/polymer/css_to_wrapper.py',
    '//tools/polymer/html_to_wrapper.py', '//third_party/node/check_version.py',
    '//third_party/node/node.py', '//third_party/lottie/minify_lottie.py',
    '//tools/protoc_wrapper/protoc_wrapper.py',
    PERMISSION_GENERATOR,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('graph', type=Path)
    parser.add_argument('--source-root', required=True, type=Path)
    args = parser.parse_args()
    graph = json.loads(gzip.decompress(args.graph.read_bytes()))
    targets = graph['targets']
    source = args.source_root.resolve()
    overlay = ROOT / 'bcr/overlay'
    reused = json.loads((ROOT / 'native/mojo_targets.json').read_text())
    reused['//third_party/protobuf:protoc'] = '//native:protoc_tool'
    grit = json.loads((overlay / 'native/grit_targets.json').read_text())['native']
    # Reuse GRIT behind the header-only GN wrapper.
    reused['//third_party/blink/public/strings:permission_element_strings'] = (
        '//native:' + grit['//third_party/blink/public/strings:permission_element_strings_grit'])
    owners = {output: label for label, target in targets.items() for output in target.get('outputs', [])}
    inputs = {'', 'build'}
    exports = {key: set() for key in inputs}
    complete, pending, running = {}, {}, set()
    records = {}

    def name(label):
        return 'webui_' + hashlib.sha256(label.encode()).hexdigest()[:16]

    def source_label(path):
        if path == NODE:
            return '@nodejs_linux_amd64//:node_bin'
        if path == BUILD + 'protoc':
            return '//native:protoc_tool'
        if path == '//third_party/protobuf/src/google/protobuf/descriptor.proto':
            return '@protobuf//:descriptor_proto_srcs'
        if path.startswith('//third_party/perfetto/protos/'):
            return '@perfetto//:' + path.removeprefix('//third_party/perfetto/')
        if path.startswith('//third_party/node/node_modules/'):
            return '@chromium_node_modules//:node_modules/' + path.removeprefix('//third_party/node/node_modules/')
        if path.startswith(BUILD):
            owner = owners.get(path)
            if path not in graph['generated_files'] and (owner is None or not visit(owner)):
                raise ValueError(f'unresolved generated input {path}: {owner}')
            return '//native:' + path.removeprefix(BUILD)
        if not path.startswith('//') or not (source / path[2:]).is_file():
            raise ValueError(f'missing WebUI source: {path}')
        relative = path[2:]
        owner = (overlay / relative).parent
        while owner != overlay and not (owner / 'BUILD.bazel').is_file():
            owner = owner.parent
        package = str(owner.relative_to(overlay)) if owner != overlay else ''
        owned = str((overlay / relative).relative_to(owner))
        exports.setdefault(package, set()).add(owned)
        return '//' + package + ':' + owned

    runtime = set()
    for directory in ['tools/grit', 'tools/typescript', 'tools/polymer', 'ui/webui/resources/tools', 'third_party/node']:
        for path in (source / directory).rglob('*.py'):
            if path.name.endswith('_unittest.py') or 'node_modules' in path.parts:
                continue
            runtime.add('//' + str(path.relative_to(source)))
    runtime.update('//build/' + name for name in ['action_helpers.py', 'gn_helpers.py', 'zip_helpers.py'])
    runtime.update('//' + str(path.relative_to(source))
                   for path in (source / 'tools/typescript').glob('tsconfig*.json'))

    def encode(paths):
        return {source_label(path): path[2:] for path in sorted(paths)}

    def visit(label):
        if label in reused:
            return True
        if label in complete:
            return True
        if label in pending:
            return False
        if label in running:
            raise ValueError(f'cyclic WebUI dependency: {label}')
        target = targets[label]
        kind = target['type']
        if kind == 'action' and target.get('script') not in SUPPORTED:
            pending[label] = 'unported script: ' + target.get('script', '')
            return False
        if kind not in ('action', 'group', 'copy', 'generated_file'):
            pending[label] = 'native prerequisite: ' + kind
            return False
        running.add(label)
        missing = [dep for dep in target.get('deps', []) if not visit(dep)]
        if missing:
            pending[label] = 'unresolved dependencies: ' + ', '.join(missing)
            running.remove(label)
            return False
        paths = set(target.get('inputs', []) + target.get('sources', []))
        if kind == 'action':
            paths.add(target['script'])
            if target['script'] == PERMISSION_GENERATOR:
                arguments = target['args']
                directory = (source / 'out/bazel-import' / arguments[arguments.index('--input_base_dir') + 1]).resolve()
                paths.add('//' + str((directory / 'permission_element_strings.grd').relative_to(source)))
                paths.update('//' + str(path.relative_to(source))
                             for path in (directory / 'translations').glob('permission_element_strings_*') if path.is_file())
            if target['script'] == '//ui/webui/resources/tools/bundle_js.py':
                arguments = target.get('args', [])
                if '--external_paths' in arguments:
                    for mapping in arguments[arguments.index('--external_paths') + 1:]:
                        if mapping.startswith('--'):
                            break
                        directory = (source / 'out/bazel-import' / mapping.split('|', 1)[1]).resolve()
                        if directory.is_relative_to(source / 'out/bazel-import'):
                            continue
                        if not directory.is_relative_to(source) or not directory.is_dir():
                            raise ValueError(f'invalid WebUI external source directory: {directory}')
                        paths.update('//' + str(path.relative_to(source))
                                     for path in directory.rglob('*') if path.is_file())
        if kind == 'generated_file':
            paths = set(target.get('outputs', []))
            if not paths <= set(graph['generated_files']):
                pending[label] = 'uncaptured generated-file contents'
                running.remove(label)
                return False
        try:
            files = encode(paths)
        except ValueError as error:
            pending[label] = str(error)
            running.remove(label)
            return False
        dependencies = [reused.get(dep, '//native:' + name(dep)) for dep in target.get('deps', [])]
        outputs = {path.removeprefix(BUILD): path.removeprefix(BUILD) for path in target.get('outputs', [])}
        if any(path.startswith('//') for path in outputs):
            raise ValueError(f'WebUI output outside build directory: {label}')
        records[label] = {'kind': kind, 'files': files, 'deps': dependencies, 'outs': outputs}
        complete[label] = '//native:' + name(label)
        running.remove(label)
        return True

    roots = [label for label, target in targets.items() if target.get('script') in (
        '//ui/webui/resources/tools/generate_grd.py', '//tools/typescript/ts_library.py', PERMISSION_GENERATOR)]
    for label in sorted(roots):
        visit(label)
    lines = ['"""Generated WebUI action graph; run tools/import_webui_actions.py."""', '',
             'load(":python_action.bzl", "chromium_python_action", "chromium_filegroup")',
             'load(":resource_copy.bzl", "chromium_resource_copy")', '',
             'load(":tool_inputs.bzl", "chromium_tool_inputs")',
             'load(":node_python_tool.bzl", "chromium_node_python_tool")',
             'load("@rules_python//python:defs.bzl", "py_binary")',
             'load("//native/rust:tools.bzl", "import_executable")', '',
             'def native_webui(name):', '    """Build original WebUI assets with declared native tools.', '',
             '    Args:', '        name: Supported asset output group.', '    """',
             '    import_executable(name = "webui_node_executable", src = "@nodejs_linux_amd64//:node_bin")',
             '    chromium_tool_inputs(name = "webui_node_inputs", tool = ":webui_node_executable", logical_path = "third_party/node/linux/node-linux-x64/bin/node")',
             '    py_binary(name = "webui_tsproto_cli", srcs = ["//:tools/protoc_wrapper/protoc-gen-ts_proto.py", "//:third_party/node/node.py", "//:third_party/node/node_modules.py"], main = "//:tools/protoc_wrapper/protoc-gen-ts_proto.py")',
             '    chromium_node_python_tool(name = "webui_tsproto_plugin", tool = ":webui_tsproto_cli", script = "//:tools/protoc_wrapper/protoc-gen-ts_proto.py", node = "@nodejs_linux_amd64//:node_bin", packages = ":node_npm_sources")',
             '    chromium_tool_inputs(name = "webui_tsproto_inputs", tool = ":webui_tsproto_plugin", logical_path = "tools/protoc_wrapper/protoc-gen-ts_proto.py")',
             '    chromium_filegroup(name = "webui_python_inputs", srcs = ' + json.dumps(encode(runtime)) + ')']
    for label, record in sorted(records.items()):
        target = targets[label]
        kind = record['kind']
        files, deps, outputs = record['files'], record['deps'], record['outs']
        if kind == 'action':
            deps = deps + ['//native:webui_python_inputs']
            if any(path.startswith('//third_party/node/') for path in target.get('inputs', [])) or target['script'].startswith((
                    '//tools/typescript/', '//tools/polymer/', '//third_party/lottie/')):
                deps += ['//native:node_npm_sources', '//native:webui_node_inputs']
                files.pop('@nodejs_linux_amd64//:node_bin', None)
            if target['script'] == '//tools/protoc_wrapper/protoc_wrapper.py':
                deps += ['//native:webui_tsproto_inputs']
                files.pop('//:tools/protoc_wrapper/protoc-gen-ts_proto.py', None)
            lines += ['    chromium_python_action(', f'        name = "{name(label)}",',
                      '        srcs = ' + json.dumps(files) + ',',
                      '        script = ' + json.dumps(target['script'][2:]) + ',',
                      '        args = ' + json.dumps(target.get('args', [])) + ',',
                      '        outs = ' + json.dumps(outputs) + ',',
                      '        propagate_inputs = True,',
                      '        deps = ' + json.dumps(sorted(set(deps))) + ',',
                      '        response_file_contents = ' + json.dumps(target.get('response_file_contents', [])) + ',', '    )']
        elif kind == 'copy':
            copies = {}
            for path, destinations in target['source_outputs'].items():
                for destination in destinations:
                    copies[destination] = path[2:]
            if set(copies) != set(outputs):
                raise ValueError(f'copy output mismatch: {label}')
            lines += ['    chromium_resource_copy(', f'        name = "{name(label)}",',
                      '        srcs = ' + json.dumps(files) + ',', '        outputs = ' + json.dumps(copies) + ',',
                      '        deps = ' + json.dumps(deps) + ',', '    )']
        else:
            lines += ['    chromium_filegroup(', f'        name = "{name(label)}",',
                      '        srcs = ' + json.dumps(files) + ',', '        deps = ' + json.dumps(deps) + ',', '    )']
    lines += ['    chromium_filegroup(name = name, deps = ' + json.dumps(list(complete.values())) + ')']
    (overlay / 'native/webui_actions.bzl').write_text('\n'.join(lines) + '\n')
    (overlay / 'native/webui_targets.json').write_text(json.dumps({'native': complete, 'pending': pending}, indent=2, sort_keys=True) + '\n')
    for package, paths in exports.items():
        if not paths:
            continue
        path = overlay / package / 'BUILD.bazel'
        replace_block(path, '# BEGIN GENERATED WEBUI INPUTS', '# END GENERATED WEBUI INPUTS',
                      'exports_files(' + json.dumps(sorted(paths), indent=4) + ')')
    module = ROOT / 'MODULE.bazel'
    text = module.read_text()
    for filename in ['webui_actions.bzl', 'webui_targets.json', 'resource_copy.bzl', 'node_python_tool.bzl']:
        mapping = f'        "native/{filename}": "//bcr/overlay/native:{filename}",\n'
        if mapping not in text:
            marker = text.index('        "native/BUILD.bazel":')
            text = text[:marker] + mapping + text[marker:]
    module.write_text(sort_archive_files(text))
    print(f'Imported {len(complete)} WebUI targets, {len(pending)} pending prerequisites')


if __name__ == '__main__':
    main()
