#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Import pinned Rust prerequisites through native rules_rust actions."""
import argparse
import gzip
import hashlib
import json
import shlex
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CXX = "third_party/rust/chromium_crates_io/vendor/cxx-v1"
HOST = '(//build/toolchain/linux:clang_x64_for_rust_host_build_tools)'
ROOTS = {
    'llguidance': '//third_party/rust/llguidance/v1:lib',
    'crabbyavif': '//third_party/crabbyavif:crabbyavif',
    'crabbyavif_libyuv_sys': '//third_party/crabbyavif:crabbyavif_libyuv_sys',
    'crabbyavif_dav1d_sys': '//third_party/crabbyavif:crabbyavif_dav1d_sys',
    'font_format_check': '//third_party/blink/renderer/platform:font_format_check',
    'blink_rust_crash': '//third_party/blink/common/rust_crash:rs',
    'cxxbridge': '//third_party/rust/cxxbridge_cmd/v1:cxxbridge' + HOST,
    'cxx_runtime': '//third_party/rust/cxx/v1:lib',
    'chromium_prelude': '//build/rust/chromium_prelude:chromium_prelude',
    'rust_log': '//third_party/rust/log/v0_4:lib',
    'serde_json_lenient': '//third_party/rust/serde_json_lenient/v0_2:lib',
    'serde': '//third_party/rust/serde/v1:lib',
    'serde_json_wrapper': '//third_party/rust/serde_json_lenient/v0_2/wrapper:wrapper',
    'rust_logger': '//base:rust_logger',
    'font_types': '//third_party/rust/font_types/v0_10:lib',
    'read_fonts': '//third_party/rust/read_fonts/v0_35:lib',
    'skrifa': '//third_party/rust/skrifa/v0_37:lib',
    'png': '//third_party/rust/png/v0_18:lib',
    'skia_fontations': '//skia:bridge_rust_side',
    'skia_png': '//skia:rust_png_ffi',
    'symphonia': '//third_party/rust/symphonia/v0_5:lib',
    'symphonia_glue': '//media/filters:symphonia_glue',
    'temporal_capi': '//third_party/rust/temporal_capi/v0_1:lib',
    'fontconfig_ffi': '//third_party/fontconfig:fontconfig_fontations_ffi',
}
BROWSER_ROOTS = {
    'qr_code_generator': '//components/qr_code_generator:qr_code_generator_ffi_glue',
    'user_data_importer_zip': '//components/user_data_importer/utility:zip_ffi_glue',
}
CPP_DEPS = {
    '//components/qr_code_generator:qr_code_generator_ffi_glue_cxx_generated': '//native:browser_' + hashlib.sha256(b'//components/qr_code_generator:qr_code_generator_ffi_glue_cxx_generated').hexdigest()[:16],
    '//components/qr_code_generator:error': '//native:browser_' + hashlib.sha256(b'//components/qr_code_generator:error').hexdigest()[:16],
    '//components/user_data_importer/utility:zip_ffi_glue_cxx_generated': '//native:browser_' + hashlib.sha256(b'//components/user_data_importer/utility:zip_ffi_glue_cxx_generated').hexdigest()[:16],
    '//third_party/crabbyavif:header_files': '@chromium_crabbyavif//:chromium_headers',
    '//third_party/dav1d:dav1d': '@dav1d//:dav1d',
    '//third_party/libyuv:libyuv': '//native:libyuv',
    '//third_party/blink/renderer/platform:font_format_check_cxx_generated': '//native:blink_rust_' + hashlib.sha256(b'//third_party/blink/renderer/platform:font_format_check_cxx_generated').hexdigest()[:16],
    '//third_party/blink/common/rust_crash:rs_cxx_generated': '//native:blink_rust_' + hashlib.sha256(b'//third_party/blink/common/rust_crash:rs_cxx_generated').hexdigest()[:16],
    '//media/filters:symphonia_glue_cxx_generated': '//native:media_' + hashlib.sha256(b'//media/filters:symphonia_glue_cxx_generated').hexdigest()[:16],
    '//skia:bridge_rust_side_cxx_generated': '//native:skia_' + hashlib.sha256(b'//skia:bridge_rust_side_cxx_generated').hexdigest()[:16],
    '//skia:path_bridge': '//native:skia_' + hashlib.sha256(b'//skia:path_bridge').hexdigest()[:16],
    '//skia:rust_png_ffi_cxx_generated': '//native:skia_' + hashlib.sha256(b'//skia:rust_png_ffi_cxx_generated').hexdigest()[:16],
    '//skia:rust_png_ffi_cpp': '//native:skia_' + hashlib.sha256(b'//skia:rust_png_ffi_cpp').hexdigest()[:16],
    '//build/rust:cxx_cppdeps': '//' + CXX + ':core-lib',
    '//third_party/rust/serde_json_lenient/v0_2/wrapper:wrapper_cxx_generated': '//native:serde_json_wrapper_cpp',
    '//third_party/rust/serde_json_lenient/v0_2/wrapper:wrapper_functions': '//:serde_json_wrapper_headers',
    '//base:debugging_buildflags': '//native:base_headers',
    '//base:tracing_buildflags': '//native:base_headers',
    '//build:chromeos_buildflags': '//native:base_headers',
    '//base/allocator/partition_allocator:raw_ptr': '//base/allocator/partition_allocator/src/partition_alloc:raw_ptr',
    '//base:rust_logger_cxx_generated': '//native:rust_logger_cpp',
}
RUST_DEPS = {
    '//third_party/crabbyavif:crabbyavif_libyuv_sys_crabbyavif_libyuv_bindings_copy': '//native/rust:crabbyavif_libyuv_bindings',
    '//third_party/crabbyavif:crabbyavif_dav1d_sys_crabbyavif_dav1d_bindings_copy': '//native/rust:crabbyavif_dav1d_bindings',
    '//base:logging_log_severity_bindgen': '//native/rust:logging_log_severity_bindgen',
    '//third_party/fontconfig:fontconfig_h_bindgen': '//native/rust:fontconfig_h_bindgen',
    '//third_party/fontconfig:fcint_h_bindgen': '//native/rust:fcint_h_bindgen',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('graph', type=Path)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--browser', action='store_true', help='Include browser QR and ZIP bridges')
    args = parser.parse_args()
    roots = ROOTS | (BROWSER_ROOTS if args.browser else {})
    graph = json.loads(gzip.decompress(args.graph.read_bytes()))
    targets = graph['targets']
    selected, scripts = {}, {}
    visited = set()

    def infrastructure(label):
        return label.startswith(('//build/rust/std:', '//buildtools/third_party/libc++:',
                                 '//build/modules/', '//build/config:executable_deps',
                                 '//build/rust/gni_impl:rustc_print_cfg'))

    def visit(label):
        if label in visited or label in CPP_DEPS or label in RUST_DEPS or infrastructure(label) or label.startswith('//build/rust/allocator:'):
            return
        visited.add(label)
        target = targets[label]
        kind = target['type']
        if kind in ('rust_library', 'rust_proc_macro') or (kind == 'executable' and target.get('crate_root')):
            selected[label] = target
        elif kind == 'action' and target.get('script') == '//build/rust/gni_impl/run_build_script.py':
            binaries = [dep for dep in target['deps'] if targets[dep].get('crate_root')]
            if len(binaries) != 1:
                raise ValueError(f'unsupported build script: {label}')
            scripts[label] = binaries[0]
        elif kind == 'action' and target.get('script') == '//build/rust/gni_impl/write_rustflags.py':
            return
        elif kind != 'group':
            raise ValueError(f'unsupported Rust dependency: {label} ({kind})')
        for dependency in target.get('deps', []):
            visit(dependency)

    for label in roots.values():
        visit(label)

    def resolve(label):
        if label in CPP_DEPS:
            return CPP_DEPS[label]
        if label in RUST_DEPS:
            return RUST_DEPS[label]
        if infrastructure(label) or label.endswith(HOST) and label.startswith('//build/rust/allocator:'):
            return None
        if label.startswith('//build/rust/allocator:'):
            return ':allocator'
        if label in scripts:
            return ':' + name(scripts[label])
        if label in selected:
            return ':' + name(label)
        target = targets[label]
        if target['type'] == 'group':
            values = list(filter(None, (resolve(dep) for dep in target.get('deps', []))))
            if len(values) != 1:
                raise ValueError(f'unsupported Rust group: {label}')
            return values[0]
        if target.get('script') == '//build/rust/gni_impl/write_rustflags.py':
            return None
        raise ValueError(f'unmapped Rust dependency: {label}')

    generated_flags = {path for label in scripts for path in targets[label]['outputs'] if path.endswith('/cargo_flags.rs')}
    script_binaries = set(scripts.values())
    sources = {'third_party/rust/serde_json_lenient/v0_2/wrapper/functions.h'}
    lines = ['"""Generated from Chromium native graph by tools/import_rust_crates.py."""', '',
             'load("@rules_rs//rs:rust_binary.bzl", "rust_binary")',
             'load("@rules_rs//rs:rust_library.bzl", "rust_library")',
             'load("@rules_rs//rs:rust_proc_macro.bzl", "rust_proc_macro")',
             'load("@rules_rs//rs:cargo_build_script.bzl", "cargo_build_script")',
             'load("@rules_cc//cc:cc_library.bzl", "cc_library")',
             'load(":bindings.bzl", "chromium_bindgen_inputs")', '',
             'def native_rust_crates(name):', '    """Build original CXX, logging, JSON, font, PNG and Temporal crates.', '', '    Args:', '        name: Compiled crate output group.', '    """',
             '    repository_root = Label("//:BUILD.bazel").workspace_root']
    for label, target in sorted(selected.items()):
        flags = target.get('rustflags', [])
        if isinstance(flags, dict):
            flags = graph['pool'][flags['pool']]
        features, retained, extra_inputs = [], [], []
        edition = None
        index = 0
        while index < len(flags):
            flag = flags[index]
            if flag.startswith('--edition='):
                edition = flag.split('=', 1)[1]
            elif flag.startswith('--cfg=feature='):
                features.append(json.loads(flag.split('=', 2)[2]))
            elif flag.startswith('@../../build/'):
                source = flag.removeprefix('@../../')
                if not (args.source_root / source).is_file():
                    raise ValueError(f'missing compiler response file: {source}')
                extra_inputs.append(source)
                retained.extend(shlex.split((args.source_root / source).read_text(), comments=True))
            elif flag.startswith('@'):
                if '//out/bazel-import/' + flag[1:] not in generated_flags:
                    raise ValueError(f'unmapped compiler response file: {flag}')
            elif flag == '--cfg':
                if not flags[index + 1].startswith('cr_rustc_revision='):
                    retained.extend(flags[index:index + 2])
                index += 1
            elif flag.startswith(('--cfg=', '-Zallow-features=', '-D', '-A', '-F', '-Cpanic=', '-Copt-level=', '-Cdebug-assertions')):
                retained.append(flag)
            index += 1
        if not edition:
            raise ValueError(f'missing edition: {label}')
        environment = dict(value.split('=', 1) for value in target.get('rustenv', []))
        environment.pop('OUT_DIR', None)
        environment.pop('CARGO_MANIFEST_DIR', None)
        root = target['crate_root'][2:]
        if root.startswith('third_party/rust/chromium_crates_io/vendor/'):
            vendor = '/'.join(root.split('/')[:5])
            crate_directory = args.source_root / vendor
            nested_packages = {path.parent for path in crate_directory.rglob('*')
                               if path.name in ('BUILD', 'BUILD.bazel') and path.parent != crate_directory}
            inventory = sorted(str(path.relative_to(args.source_root)) for path in crate_directory.rglob('*')
                               if path.is_file() and path.name not in ('BUILD', 'BUILD.bazel')
                               and not any(path.is_relative_to(package) for package in nested_packages))
        else:
            vendor = None
            inventory = [path[2:] for path in target['sources']]
        if not inventory or any(not (args.source_root / path).is_file() for path in inventory):
            raise ValueError(f'missing source inventory: {label}')
        sources.update(inventory + extra_inputs)
        dependencies, macros, link_dependencies = [], [], []
        for dep in target.get('deps', []):
            value = resolve(dep)
            if not value:
                continue
            if dep in CPP_DEPS:
                link_dependencies.append(value)
                continue
            resolved = next((key for key in selected if ':' + name(key) == value), None)
            if resolved and targets[resolved]['type'] == 'rust_proc_macro':
                macros.append(value)
            else:
                dependencies.append(value)
        if label in script_binaries:
            rule = 'cargo_build_script'
            # Script activation follows its library's exact feature set.
            owners = [owner for owner in selected.values() if any(scripts.get(dep) == label for dep in owner.get('deps', []))]
            owner_flags = owners[0].get('rustflags', []) if owners else []
            if isinstance(owner_flags, dict):
                owner_flags = graph['pool'][owner_flags['pool']]
            features = [json.loads(flag.split('=', 2)[2]) for flag in owner_flags if flag.startswith('--cfg=feature=')]
        else:
            rule = {'rust_library': 'rust_library', 'rust_proc_macro': 'rust_proc_macro', 'executable': 'rust_binary'}[target['type']]
        script_directories = {
            str(Path(output).parent) + '/'
            for dep in target.get('deps', []) if dep in scripts
            for output in targets[dep]['outputs'] if output.endswith('/cargo_flags.rs')
        }
        crate_sources = []
        for path in target['sources']:
            if path.startswith('//out/bazel-import/'):
                if not any(path.startswith(directory) for directory in script_directories):
                    raise ValueError(f'unmapped generated Rust source: {path}')
                continue
            crate_sources.append(file_label(path[2:]))
        attrs = {'name': name(label), 'crate_name': target['crate_name'], 'crate_root': file_label(root),
                 'srcs': crate_sources, 'edition': edition,
                 'crate_features': sorted(features), 'rustc_flags': retained, 'rustc_env': environment,
                 'deps': sorted(set(dependencies)), 'proc_macro_deps': sorted(set(macros))}
        if vendor or extra_inputs:
            attrs['compile_data'] = [file_label(path) for path in inventory + extra_inputs]
        if label == ROOTS['cxx_runtime']:
            link_dependencies.append('//' + CXX + ':core-lib')
        if link_dependencies:
            attrs['link_deps'] = sorted(set(link_dependencies))
        if rule == 'cargo_build_script':
            attrs['version'] = environment.get('CARGO_PKG_VERSION', '')
            attrs['pkg_name'] = environment.get('CARGO_PKG_NAME', '')
            attrs['data'] = [file_label(path) for path in inventory]
            attrs['use_default_shell_env'] = False
        lines += [f'    {rule}('] + [f'        {key} = {str(value) if isinstance(value, bool) else json.dumps(value, ensure_ascii=False)},' for key, value in attrs.items()]
        if rule == 'cargo_build_script':
            lines += [f'        build_script_env = {{"CARGO_MANIFEST_DIR": repository_root + "/{vendor}"}},']
        lines += ['    )']
    for library, cc_lib in [('dav1d', '@dav1d//:dav1d'), ('libyuv', '//native:libyuv')]:
        label = '//third_party/crabbyavif:crabbyavif_' + library + '_bindings'
        target = targets[label]
        arguments = target['args']
        filters = arguments[arguments.index('--bindgen-flags') + 1:arguments.index('--')]
        lines += [
            '    cc_library(',
            '        name = "crabbyavif_' + library + '_bindgen_headers",',
            '        hdrs = [' + json.dumps(file_label(target['sources'][0][2:])) + '],',
            '        deps = [' + json.dumps(cc_lib) + '],',
            '    )',
            '    chromium_bindgen_inputs(',
            '        name = "crabbyavif_' + library + '_bindings",',
            '        header = ' + json.dumps(file_label(target['sources'][0][2:])) + ',',
            '        cc_lib = ":crabbyavif_' + library + '_bindgen_headers",',
            '        bindgen_flags = ' + json.dumps(['--' + flag for flag in filters]) + ',',
            '        clang_flags = ["-x", "c", "-std=c17"],',
            '        output_name = "' + library + '_bindgen.rs",',
            '    )',
        ]
    for alias, label in roots.items():
        lines += [f'    native.alias(name = "{alias}", actual = "{resolve(label)}")']
    temporal_directory = 'third_party/rust/chromium_crates_io/vendor/temporal_capi-v0_1/bindings/cpp'
    temporal_headers = sorted(path for path in sources if path.startswith(temporal_directory + '/') and path.endswith(('.h', '.hpp')))
    if not temporal_headers:
        raise ValueError('missing Temporal C++ bindings')
    lines += [
        '    cc_library(',
        '        name = "temporal_capi_headers",',
        '        hdrs = ' + json.dumps([file_label(path) for path in temporal_headers]) + ',',
        '        includes = ["../../' + temporal_directory + '"],',
        '        defines = ["TEMPORAL_CAPI_VERSION_0_1"],',
        '    )',
        '    cc_library(name = "temporal_capi_cpp", deps = [":temporal_capi_headers", ":temporal_capi"])',
    ]
    lines += ['    native.filegroup(name = name, srcs = ' + json.dumps([':' + alias for alias in roots]) + ')']
    (ROOT / 'bcr/overlay/native/rust/crates.bzl').write_text('\n'.join(lines) + '\n')
    for relative, owned in [('bcr/overlay/BUILD.bazel', [p for p in sources if not p.startswith(('build/', CXX + '/', 'third_party/fontconfig/src/', 'third_party/skia/', 'third_party/crabbyavif/src/'))]),
                            ('bcr/overlay/build/BUILD.bazel', [p.removeprefix('build/') for p in sources if p.startswith('build/')])]:
        path = ROOT / relative
        text = path.read_text()
        begin, end = '# BEGIN GENERATED RUST INPUTS', '# END GENERATED RUST INPUTS'
        block = begin + '\nexports_files(' + json.dumps(sorted(owned), indent=4) + ')\n' + end
        if begin in text:
            before, rest = text.split(begin, 1)
            _, after = rest.split(end, 1)
            text = before + block + after
        else:
            text += '\n' + block + '\n'
        path.write_text(text)
    cxx_package = ROOT / 'bcr/overlay' / CXX
    cxx_package.mkdir(parents=True, exist_ok=True)
    cxx_files = sorted(path.removeprefix(CXX + '/') for path in sources if path.startswith(CXX + '/'))
    (cxx_package / 'BUILD.bazel').write_text(
        'load("@rules_cc//cc:cc_library.bzl", "cc_library")\n'
        + 'package(default_visibility = ["//visibility:public"])\n'
        + 'exports_files(' + json.dumps(cxx_files + ['BUILD.bazel'], indent=4) + ')\n'
        + 'cc_library(name = "core", hdrs = ["include/cxx.h"], include_prefix = "rust", strip_include_prefix = "include")\n'
        + 'cc_library(name = "core-lib", srcs = ["src/cxx.cc"], hdrs = ["include/cxx.h"], defines = ["CXX_RS_EXPORT="], copts = ["-std=c++20", "-fno-exceptions", "-fno-rtti"], linkstatic = True, deps = [":core", "//:cxx_wrapper_headers"])\n')
    print(f'Imported {len(selected)} Rust targets, {len(scripts)} build scripts, {len(sources)} source inputs')


def name(label):
    return 'crate_' + hashlib.sha256(label.encode()).hexdigest()[:16]


def file_label(path):
    if path.startswith('third_party/crabbyavif/src/'):
        return '@chromium_crabbyavif//:' + path.removeprefix('third_party/crabbyavif/src/')
    if path.startswith('third_party/skia/'):
        return '@chromium_skia//:' + path
    if path.startswith('third_party/fontconfig/src/'):
        return '@chromium_fontconfig//:' + path.removeprefix('third_party/fontconfig/src/')
    if path.startswith(CXX + '/'):
        return '//' + CXX + ':' + path.removeprefix(CXX + '/')
    return '//build:' + path.removeprefix('build/') if path.startswith('build/') else '//:' + path


if __name__ == '__main__':
    main()
