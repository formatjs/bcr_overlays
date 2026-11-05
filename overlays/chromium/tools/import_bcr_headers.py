#!/usr/bin/env python3
"""Bridge Chromium's original include paths to shared BCR implementations."""
import argparse
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIBRARIES = {
    'abseil-cpp': ('third_party/abseil-cpp', 'absl'),
    'boringssl': ('third_party/boringssl', 'src/include/openssl'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('graph', type=Path)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--abseil-source', type=Path, required=True)
    parser.add_argument('--boringssl-source', type=Path, required=True)
    args = parser.parse_args()
    graph = json.loads(gzip.decompress(args.graph.read_bytes()))
    mapped = []
    for module, (relative, include) in LIBRARIES.items():
        upstream = args.source_root / relative
        output = ROOT / 'bcr/overlay' / relative
        packages = {}
        labels = []
        headers = list((upstream / include).rglob('*.h'))
        if module == 'boringssl':
            headers += [path for path in (upstream / 'src/pki').rglob('*.h')
                        if (args.boringssl_source / path.relative_to(upstream / 'src')).is_file()]
        for header in sorted(headers):
            suffix = header.relative_to(upstream)
            if module == 'abseil-cpp':
                canonical = str(suffix)
            elif header.is_relative_to(upstream / include):
                canonical = 'openssl/' + str(header.relative_to(upstream / include))
            else:
                canonical = str(header.relative_to(upstream / 'src'))
            if module == 'abseil-cpp' and not (args.abseil_source / canonical).is_file():
                continue
            owner = header.parent
            while owner != upstream and not any((owner / name).is_file() for name in ('BUILD.bazel', 'BUILD')):
                owner = owner.parent
            package = owner.relative_to(upstream)
            target = output / suffix
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('#include "' + canonical + '"\n')
            packages.setdefault(package, []).append(str(header.relative_to(owner)))
            labels.append('//' + str(Path(relative) / package) + ':' + str(header.relative_to(owner)))
        for package, headers in packages.items():
            directory = output / package
            directory.mkdir(parents=True, exist_ok=True)
            (directory / 'BUILD.bazel').write_text('exports_files(' + json.dumps(headers + ['BUILD.bazel'], indent=4) + ', visibility = ["//visibility:public"])\n')
        output.mkdir(parents=True, exist_ok=True)
        if module == 'abseil-cpp':
            dependencies = [label.replace('//third_party/abseil-cpp/', '@abseil-cpp//') for label in graph['targets']['//third_party/abseil-cpp:absl_component_deps']['deps']]
            facade = ROOT.parent / 'abseil-cpp/bcr/overlay/absl/chromium'
            facade.mkdir(parents=True, exist_ok=True)
            (facade / 'BUILD.bazel').write_text('load("@rules_cc//cc:cc_library.bzl", "cc_library")\ncc_library(name = "absl", deps = '
                + json.dumps([label.replace('@abseil-cpp//', '//') for label in dependencies])
                + ', visibility = ["//visibility:public"])\n')
            dependencies = ['@abseil-cpp//absl/chromium:absl']
        else:
            dependencies = ['@boringssl//:crypto', '@boringssl//:ssl', '@boringssl//:chromium_pki']
        (output / 'BUILD.bazel').write_text('load("@rules_cc//cc:cc_library.bzl", "cc_library")\n'
            + 'cc_library(name = ' + json.dumps('absl' if module == 'abseil-cpp' else 'boringssl')
            + ', hdrs = ' + json.dumps(labels) + ', includes = ["../.."], deps = ' + json.dumps(dependencies)
            + ', visibility = ["//visibility:public"])\nexports_files(["BUILD.bazel"])\n')
        for path in sorted(output.rglob('*')):
            if not path.is_file():
                continue
            owner = path.parent
            while not (owner / 'BUILD.bazel').is_file():
                owner = owner.parent
            destination = str(path.relative_to(ROOT / 'bcr/overlay'))
            source = '//bcr/overlay/' + str(owner.relative_to(ROOT / 'bcr/overlay')) + ':' + str(path.relative_to(owner))
            mapped.append((destination, source))
        print(module, len(labels), 'forwarding headers')
    path = ROOT / 'MODULE.bazel'
    text = path.read_text()
    lines = [line for line in text.splitlines() if not any(line.strip().startswith('"' + relative + '/') for relative, _ in LIBRARIES.values())]
    marker = '        "native/BUILD.bazel":'
    index = next(i for i, line in enumerate(lines) if line.startswith(marker))
    lines[index:index] = [f'        {json.dumps(dest)}: {json.dumps(source)},' for dest, source in mapped]
    path.write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
