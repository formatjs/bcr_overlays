#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Pin Chromium's Node binary and complete prepatched WebUI source archive."""

import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parents[1]))
from tools.read_deps import parse_deps


def main():
    source = Path(sys.argv[1])
    archive = parse_deps((source / 'DEPS').read_text())['deps']['src/third_party/node/node_modules']
    if archive['dep_type'] != 'gcs' or len(archive['objects']) != 1:
        raise ValueError('unsupported Node source archive')
    record = archive['objects'][0]
    metadata = {
        'url': f'https://storage.googleapis.com/{archive["bucket"]}/{record["object_name"]}?generation={record["generation"]}',
        'sha256': record['sha256sum'],
        'size_bytes': record['size_bytes'],
    }
    output = ROOT / 'bcr/overlay/native/npm_packages.bzl'
    output.write_text('"""Exact prepatched WebUI Node source archive from Chromium DEPS."""\n\n' +
                      'NODE_MODULES_ARCHIVE = ' + json.dumps(metadata, indent=4) + '\n')
    version = re.search(r'^NODE_VERSION="v([0-9.]+)"',
                        (source / 'third_party/node/update_node_binaries').read_text(), re.M).group(1)
    for relative in ['MODULE.bazel', 'bcr/MODULE.bazel', 'bcr/overlay/MODULE.bazel']:
        path = ROOT / relative
        start, end = '# BEGIN CHROMIUM NODE DEPENDENCIES', '# END CHROMIUM NODE DEPENDENCIES'
        text = path.read_text()
        if start in text:
            before, remaining = text.split(start, 1)
            _, after = remaining.split(end, 1)
            text = before + after
        extension = '//bcr/overlay/native:node_deps.bzl' if relative == 'MODULE.bazel' else '//native:node_deps.bzl'
        lines = [start, 'bazel_dep(name = "rules_nodejs", version = "6.7.7")', '',
                 'node = use_extension("@rules_nodejs//nodejs:extensions.bzl", "node")',
                 f'node.toolchain(node_version = "{version}")',
                 'use_repo(node, "nodejs_linux_amd64")', '',
                 f'npm_sources = use_extension("{extension}", "npm_sources")',
                 'use_repo(npm_sources, "chromium_node_modules")', end]
        path.write_text(text.rstrip() + '\n\n' + '\n'.join(lines) + '\n')
    print(f'Pinned Node {version}, complete prepatched Node sources ({record["size_bytes"]} archive bytes)')


if __name__ == '__main__':
    main()
