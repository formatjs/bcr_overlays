#!/usr/bin/env python3
"""Import Perfetto's upstream native host compiler graph without running GN."""
import argparse
import ast
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'bcr/overlay/host_sources.bzl')
    args = parser.parse_args()
    tree = ast.parse((args.source / 'BUILD').read_text())
    names = ['src_base_base', 'perfetto_base_default_platform', 'include_perfetto_base_base',
             'include_perfetto_ext_base_base', 'include_perfetto_public_abi_base', 'include_perfetto_public_base',
             'protozero', 'include_perfetto_protozero_protozero', 'include_perfetto_public_protozero']
    result = {}
    for node in tree.body:
        if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
            continue
        call = node.value
        fields = {field.arg: field.value for field in call.keywords}
        if 'name' not in fields or not isinstance(fields['name'], ast.Constant):
            continue
        name = fields['name'].value
        if name not in names:
            continue
        result[name.upper()] = ast.literal_eval(fields.get('srcs', fields.get('hdrs')))
    if len(result) != len(names):
        raise ValueError('upstream host graph changed')
    for paths in result.values():
        for path in paths:
            if path.startswith(':') or not (args.source / path).is_file():
                raise ValueError(f'unsupported source: {path}')
    args.output.write_text('"""Generated from pinned upstream BUILD by tools/import_host_tools.py."""\n\n' +
                           '\n\n'.join(f'{name} = {paths!r}' for name, paths in sorted(result.items())) + '\n')


if __name__ == '__main__':
    main()
