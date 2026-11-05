#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build each compatibility module without the other consumer dependencies."""

import argparse
import ast
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]


def calls(text, function):
    for node in ast.parse(text).body:
        if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name) and node.value.func.id == function):
            yield node, {key.arg: ast.literal_eval(key.value) for key in node.value.keywords}


def consumer_cases(source):
    groups = [value['srcs'] for _, value in calls((source/'BUILD.bazel').read_text(), 'filegroup')
              if value['name'] == 'libraries']
    targets = {}
    for label in groups[0]:
        name = label[1:].split('//')[0]
        if not label.startswith('@') or not re.fullmatch(r'[a-z][a-z0-9._-]*', name):
            raise ValueError(f'invalid consumer label: {label}')
        targets.setdefault(name, []).append(label)
    template = (source/'MODULE.bazel').read_text()
    lines = template.splitlines(keepends=True)
    dependencies = list(calls(template, 'bazel_dep'))
    result = {}
    for name, labels in targets.items():
        omitted = {index for node, value in dependencies
                   if value['name'] in targets and value['name'] != name
                   for index in range(node.lineno - 1, node.end_lineno)}
        module = ''.join(line for index, line in enumerate(lines) if index not in omitted)
        result[name] = dict(module=module, targets=labels)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bazel', default='bazel')
    parser.add_argument('--work-dir', type=Path)
    parser.add_argument('--module', nargs='+')
    parser.add_argument('bazel_args', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    source = ROOT / 'compatibility_registry/tests'
    cases = consumer_cases(source)
    selected = args.module or sorted(cases)
    if set(selected) - cases.keys():
        parser.error('unknown compatibility module')
    work = (args.work_dir or Path(tempfile.mkdtemp(prefix='chromium-compatibility-'))).resolve()
    consumer = work / 'consumer'
    consumer.mkdir(parents=True, exist_ok=True)
    if (consumer/'MODULE.bazel').exists():
        parser.error('consumer directory already exists; choose a fresh work directory')
    shutil.copyfile(source/'.bazelversion', consumer/'.bazelversion')
    configuration = (source/'.bazelrc').read_text()
    configuration, count = re.subn(r'(?m)^startup --host_jvm_args=-Xmx.*$',
                                   'startup --host_jvm_args=-Xmx2g', configuration)
    if count != 1:
        raise ValueError('expected one consumer JVM heap limit')
    (consumer/'.bazelrc').write_text(configuration)
    (consumer/'BUILD.bazel').write_text('')
    extra = args.bazel_args[1:] if args.bazel_args[:1] == ['--'] else args.bazel_args
    results = []
    print(f'Consumer logs: {work}', flush=True)
    for name in selected:
        case = cases[name]
        (consumer/'MODULE.bazel').write_text(case['module'])
        command = [args.bazel, '--batch', '--output_user_root=' + str(work/'bazel'),
                   'build', '--keep_going',
                   '--registry=' + (ROOT/'compatibility_registry').as_uri(),
                   '--registry=https://bcr.bazel.build', *extra, *case['targets']]
        start = time.monotonic()
        with (work/(name + '.log')).open('w') as log:
            result = subprocess.run(command, cwd=consumer, stdout=log, stderr=subprocess.STDOUT)
        results.append(dict(module=name, targets=case['targets'], returncode=result.returncode))
        (work/'results.json').write_text(json.dumps(results, indent=2) + '\n')
        verdict = 'PASS' if result.returncode == 0 else 'FAIL'
        print(f'{name}: {verdict} ({time.monotonic() - start:.1f}s)', flush=True)
    return int(any(result['returncode'] for result in results))


if __name__ == '__main__':
    raise SystemExit(main())
