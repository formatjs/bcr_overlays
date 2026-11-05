#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Import native GRIT resource actions and report unresolved asset producers."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

from import_base import sort_archive_files

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {
    '//ui/strings:ui_strings_grit': 'grit_ui_strings',
    '//chrome/app:generated_resources_grit': 'grit_generated_resources',
    '//chrome/app:branded_strings_grit': 'grit_branded_strings',
    '//chrome/app/resources:locale_settings_grit': 'grit_locale_settings',
    '//chrome/app/resources:platform_locale_settings_grit': 'grit_platform_locale_settings',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('graph', type=Path)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--generated-root', type=Path,
                        help='Native output directory after browser, WebUI and inspector asset builds; input discovery only')
    args = parser.parse_args()
    graph = json.loads(gzip.decompress(args.graph.read_bytes()))
    source = args.source_root.resolve()
    overlay = ROOT / 'bcr/overlay'
    build = source / 'out/bazel-import'
    sys.path.insert(0, str(source / 'tools/grit'))
    import grit_info
    from grit import util, exception
    proto_actions = json.loads((overlay / 'native/perfetto_proto_targets.json').read_text())
    mojo_actions = json.loads((ROOT / 'native/mojo_targets.json').read_text())
    webui_actions = json.loads((overlay / 'native/webui_targets.json').read_text())['native']
    for filename in ['devtools_inspector_targets.json', 'browser_targets.json']:
        catalog = overlay / 'native' / filename
        if catalog.exists():
            webui_actions.update({label: '//native:' + name for label, name in json.loads(catalog.read_text()).items()})
    native_outputs = set(graph['generated_files'])
    for target in set(proto_actions) | set(mojo_actions) | set(webui_actions):
        native_outputs.update(graph['targets'][target].get('outputs', []))
    producers = {output: target for target, value in graph['targets'].items()
                 for output in value.get('outputs', [])}
    if args.generated_root:
        for path in sorted(native_outputs):
            relative = path.removeprefix('//out/bazel-import/')
            artifact = args.generated_root / relative
            if not artifact.is_file():
                if producers.get(path) in webui_actions and path not in graph['generated_files']:
                    raise FileNotFoundError(f'missing native asset output: {artifact}')
                continue
            destination = build / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.unlink(missing_ok=True)
            shutil.copyfile(artifact, destination)
    selected, pending = {}, {}

    class UnmappedInput(Exception):
        pass

    def generated_input(path):
        if path not in native_outputs:
            raise UnmappedInput(f'{path}: producer {producers.get(path, "unknown")}')
        relative = path.removeprefix('//out/bazel-import/')
        return ':' + relative, 'out/bazel-import/' + relative
    command = [sys.executable, str(source / 'tools/grit/grit.py'), 'update_resource_ids',
               '--input', str(source / 'tools/gritsettings/resource_ids.spec')]
    id_inputs = subprocess.check_output(command + ['--analyze-inputs'], text=True).splitlines()
    inputs = {'tools/gritsettings/resource_ids.spec'}
    inputs.update(str(Path(path).relative_to(source)) for path in id_inputs)
    python_sources = sorted(str(path.relative_to(source)) for path in (source / 'tools/grit').rglob('*.py')
                            if not path.name.endswith('_unittest.py'))
    inputs.update(python_sources)

    def part_closure(paths):
        result = set(paths)
        pending = list(result)
        while pending:
            relative = pending.pop()
            if Path(relative).suffix not in ('.grd', '.grdp'):
                continue
            path = source / relative
            for node in ET.parse(path).iter('part'):
                child = (path.parent / os.path.expandvars(node.attrib['file'])).resolve()
                if not child.is_file():
                    if child.is_relative_to(build):
                        raise UnmappedInput('generated fragment: //' + str(child.relative_to(source)))
                    raise ValueError(f'missing GRIT fragment: {child}')
                owned = str(child.relative_to(source))
                if owned not in result:
                    result.add(owned)
                    pending.append(owned)
        return result

    inputs = part_closure(inputs)

    def label(path):
        if path.startswith('third_party/devtools-frontend/src/'):
            return '@chromium_devtools_frontend//:' + path.removeprefix('third_party/devtools-frontend/src/')
        if path.startswith('third_party/dom_distiller_js/dist/'):
            return '@chromium_dom_distiller_js//:' + path.removeprefix('third_party/dom_distiller_js/dist/')
        if path.startswith('third_party/readability/src/'):
            return '@chromium_readability//:' + path.removeprefix('third_party/readability/src/')
        if path.startswith('third_party/node/node_modules/'):
            return '@chromium_node_modules//:node_modules/' + path.removeprefix('third_party/node/node_modules/')
        if path.startswith('third_party/perfetto/protos/'):
            return '@perfetto//:' + path.removeprefix('third_party/perfetto/')
        owner = (overlay / path).parent
        while owner != overlay and not (owner / 'BUILD.bazel').is_file():
            owner = owner.parent
        if owner != overlay:
            raise ValueError(f'GRIT input crosses existing package: {path}')
        return '//:' + path

    lines = ['"""Generated native GRIT actions; run tools/import_grit_actions.py."""', '',
             'load(":python_action.bzl", "chromium_python_action")',
             'load(":tool_inputs.bzl", "chromium_tool_inputs")', '',
             'def native_grit(name):', '    """Generate original browser resource packs with native host tools.', '',
             '    Args:', '        name: Generated resource output group.', '    """',
             '    chromium_python_action(', '        name = "grit_resource_ids",',
             '        srcs = ' + json.dumps({label(path): path for path in sorted(inputs)}) + ',',
             '        script = "tools/grit/grit.py",',
             '        args = ' + json.dumps(graph['targets']['//tools/gritsettings:default_resource_ids']['args']) + ',',
             '        outs = {"gen/tools/gritsettings/default_resource_ids": "gen/tools/gritsettings/default_resource_ids"},', '    )',
             '    chromium_tool_inputs(name = "grit_brotli_tool", tool = "@brotli//:brotli", logical_path = "out/bazel-import/brotli")']
    all_outputs = [':gen/tools/gritsettings/default_resource_ids']
    with tempfile.TemporaryDirectory(prefix='chromium-grit-discovery.') as temporary:
        ids = Path(temporary) / 'resource_ids'
        subprocess.run(command + ['--add-header', '-o', str(ids)], check=True)
        previous = Path.cwd()
        os.chdir(build)
        try:
            for target_label, target in sorted(graph['targets'].items()):
                if target.get('script') != '//tools/grit/grit.py':
                    continue
                name = TARGETS.get(target_label, 'grit_' + hashlib.sha256(target_label.encode()).hexdigest()[:16])
                arguments = target['args']
                if target_label == '//tools/gritsettings:default_resource_ids':
                    selected[target_label] = 'grit_resource_ids'
                    continue
                defines = {}
                for index, argument in enumerate(arguments[:-1]):
                    if argument == '-D':
                        key, value = util.ParseDefine(arguments[index + 1])
                        defines[key] = value
                    elif argument == '-E':
                        key, value = arguments[index + 1].split('=', 1)
                        os.environ[key] = value
                grd = (build / arguments[arguments.index('-i') + 1]).resolve()
                raw = set(target.get('inputs', []))
                deps = [':grit_resource_ids']
                additions = set()
                try:
                    if grd.is_relative_to(build):
                        path = '//' + str(grd.relative_to(source))
                        generated_input(path)
                        if not grd.is_file():
                            raise UnmappedInput(f'generated GRD needs native build artifact: {path}')
                    for path in raw:
                        if path.startswith('//out/') and path not in (
                                '//out/bazel-import/brotli', '//out/bazel-import/gen/tools/gritsettings/default_resource_ids'):
                            generated_input(path)
                    discovered = grit_info.Inputs(str(grd), defines, str(ids), target_platform='linux')
                    files = {label(path): path for path in python_sources}
                    for path in discovered:
                        absolute = (build / path).resolve()
                        if absolute != ids:
                            raw.add('//' + str(absolute.relative_to(source)))
                    fragments = part_closure(path[2:] for path in raw if not path.startswith('//out/'))
                    raw.update('//' + path for path in fragments)
                    for path in sorted(raw):
                        if path == '//out/bazel-import/gen/tools/gritsettings/default_resource_ids':
                            continue
                        if path == '//out/bazel-import/brotli':
                            deps.append(':grit_brotli_tool')
                        elif path.startswith('//out/bazel-import/'):
                            file_label, logical = generated_input(path)
                            files[file_label] = logical
                            producer = producers.get(path)
                            if producer in webui_actions:
                                deps.append(webui_actions[producer])
                        else:
                            relative = path.removeprefix('//')
                            if not (source / relative).is_file():
                                raise FileNotFoundError(f'missing GRIT input: {relative}')
                            file_label = label(relative)
                            if file_label.startswith('//:'):
                                additions.add(relative)
                            files[file_label] = relative
                except (UnmappedInput, FileNotFoundError, exception.FileNotFound) as error:
                    pending[target_label] = str(error).replace(str(source), '$SOURCE_ROOT')
                    continue
                inputs.update(additions)
                selected[target_label] = name
                outputs = {path.removeprefix('//out/bazel-import/'): path.removeprefix('//out/bazel-import/')
                           for path in target['outputs']}
                all_outputs.extend(':' + path for path in outputs)
                lines += ['    chromium_python_action(', f'        name = "{name}",',
                          '        srcs = ' + json.dumps(files) + ',',
                          '        script = "tools/grit/grit.py",',
                          '        args = ' + json.dumps(arguments) + ',',
                          '        outs = ' + json.dumps(outputs) + ',',
                          '        deps = ' + json.dumps(sorted(set(deps))) + ',', '    )']
        finally:
            os.chdir(previous)
    lines += ['    native.filegroup(name = name, srcs = ' + json.dumps([':' + name for name in selected.values()]) + ')']
    (overlay / 'native/grit_actions.bzl').write_text('\n'.join(lines) + '\n')
    (overlay / 'native/grit_sources.bzl').write_text('"""Original GRIT Python runtime inputs."""\nROOT_PYS = ' + json.dumps(python_sources, indent=4) + '\n')
    (overlay / 'native/grit_targets.json').write_text(json.dumps({'native': selected, 'pending': pending}, indent=2) + '\n')
    path = overlay / 'BUILD.bazel'
    text = path.read_text()
    begin, end = '# BEGIN GENERATED GRIT INPUTS', '# END GENERATED GRIT INPUTS'
    block = begin + '\nexports_files(' + json.dumps(sorted(inputs), indent=4) + ')\n' + end
    if begin in text:
        before, rest = text.split(begin, 1)
        _, after = rest.split(end, 1)
        text = before + block + after
    else:
        text += '\n' + block + '\n'
    path.write_text(text)
    module = ROOT / 'MODULE.bazel'
    text = module.read_text()
    marker = '        "native/BUILD.bazel":'
    for filename in ['grit_actions.bzl', 'grit_sources.bzl', 'grit_targets.json']:
        mapping = f'        "native/{filename}": "//bcr/overlay/native:{filename}",\n'
        if mapping not in text:
            index = text.index(marker)
            text = text[:index] + mapping + text[index:]
    module.write_text(sort_archive_files(text))
    print(f'Imported {len(selected)} GRIT actions including shared IDs, {len(all_outputs)} outputs, {len(inputs)} source inputs; {len(pending)} actions pending')


if __name__ == '__main__':
    main()
