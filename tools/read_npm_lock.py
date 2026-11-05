#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Read installed dependency paths from an npm package-lock without executing npm."""

from pathlib import PurePosixPath


def dependency_closure(lock, entry):
    packages = lock['packages']
    if lock.get('lockfileVersion') not in (2, 3):
        raise ValueError('requires package-lock version 2 or 3')
    result = {}

    def resolve(parent, name):
        for directory in (PurePosixPath(parent), *PurePosixPath(parent).parents):
            if directory.name == 'node_modules':
                continue
            candidate = str(directory / 'node_modules' / name)
            if candidate in packages:
                return candidate
        raise ValueError(f'unresolved dependency: {parent}: {name}')

    def visit(path):
        if path in result:
            return
        if not path.startswith('node_modules/') or '..' in PurePosixPath(path).parts:
            raise ValueError(f'invalid package path: {path}')
        record = packages[path]
        if record.get('link') or record.get('hasInstallScript'):
            raise ValueError(f'unsupported package setup: {path}')
        if not record.get('resolved', '').startswith('https://registry.npmjs.org/'):
            raise ValueError(f'unsupported package source: {path}')
        if not record.get('integrity', '').startswith(('sha512-', 'sha256-')):
            raise ValueError(f'missing package integrity: {path}')
        result[path] = {key: record[key] for key in ('version', 'resolved', 'integrity')}
        for name in record.get('dependencies', {}):
            visit(resolve(path, name))
        if record.get('optionalDependencies') or record.get('peerDependencies'):
            raise ValueError(f'optional or peer dependency mapping required: {path}')

    visit(resolve('', entry))
    return dict(sorted(result.items()))
