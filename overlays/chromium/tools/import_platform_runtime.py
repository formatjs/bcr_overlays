#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Find runtime package requirements from pinned SDK link interfaces."""

import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.parse import unquote
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
# Use the execution platform's glibc and loader, matching LLVM's Linux ABI floor.
SYSTEM_LIBRARIES = {
    'ld-linux-x86-64.so.2', 'libc.so.6', 'libm.so.6', 'libdl.so.2',
    'libpthread.so.0', 'librt.so.1', 'libresolv.so.2', 'libutil.so.1',
}
NATIVE_LIBRARIES = {'libpci.so.3': '@chromium_pciutils//:libpci.so.3'}
NATIVE_LIBRARIES.update({'lib' + name + '.so': '@nss//:lib' + name + '.so'
                         for name in ['freebl3', 'freeblpriv3', 'nss3', 'nssckbi',
                                      'nssdbm3', 'nssutil3', 'smime3', 'softokn3', 'ssl3']})
NATIVE_LIBRARIES.update({'lib' + name + '.so': '@nspr//:lib' + name + '.so'
                         for name in ['nspr4', 'plc4', 'plds4']})
BAZEL_LIBRARIES = {
    **NATIVE_LIBRARIES,
    'libglib-2.0.so.0': '@glib//glib:libglib-2.0.so.0',
    'libgobject-2.0.so.0': '@glib//gobject:libgobject-2.0.so.0',
    'libgio-2.0.so.0': '@glib//gio:libgio-2.0.so.0',
    'libgmodule-2.0.so.0': '@glib//gmodule:libgmodule-2.0.so.0',
}


def dynamic(path):
    result = subprocess.run(['readelf', '-d', str(path)], text=True, capture_output=True)
    if result.returncode:
        raise ValueError(f'cannot inspect {path}: {result.stderr.strip()}')
    output = result.stdout
    needed = re.findall(r'\(NEEDED\).*?\[(.*?)\]', output)
    sonames = re.findall(r'\(SONAME\).*?\[(.*?)\]', output)
    if len(sonames) != 1:
        raise ValueError(f'expected one shared-library SONAME: {path}')
    return sonames[0], needed


def package_urls(url):
    suffix = url.split('/pool/', 1)[1]
    return ['https://archive.debian.org/debian/pool/' + suffix,
            'https://deb.debian.org/debian/pool/' + suffix, url]


def download_packages(libraries, directory):
    archives = directory / 'packages'
    extracted = directory / 'root'
    archives.mkdir(parents=True, exist_ok=True)
    extracted.mkdir(parents=True, exist_ok=True)
    urls = sorted({row['url'] for row in libraries.values()})

    def download(url):
        archive = archives / unquote(url.rsplit('/', 1)[-1])
        if not archive.exists():
            temporary = archive.with_suffix('.partial')
            for mirror in package_urls(url):
                for attempt in range(3):
                    try:
                        with urlopen(mirror, timeout=30) as response, temporary.open('wb') as destination:
                            while block := response.read(1024 * 1024):
                                destination.write(block)
                        temporary.replace(archive)
                        break
                    except (URLError, TimeoutError) as error:
                        if isinstance(error, HTTPError) and error.code < 500 and error.code != 429:
                            break
                        if attempt < 2:
                            time.sleep(2 ** attempt)
                if archive.exists():
                    break
            if not archive.exists():
                raise RuntimeError(f'Debian package unavailable: {url}')
        return url, archive, hashlib.sha256(archive.read_bytes()).hexdigest()

    with ThreadPoolExecutor(max_workers=8) as workers:
        packages = list(workers.map(download, urls))
    for _, archive, _ in packages:
        subprocess.run(['dpkg-deb', '-x', str(archive), str(extracted)], check=True)
    for soname, row in libraries.items():
        path = extracted / row['interface']
        if hashlib.md5(path.read_bytes()).hexdigest() != row['md5']:
            raise ValueError(f'original package checksum mismatch: {soname}')
        sections = subprocess.check_output(['readelf', '-SW', str(path)], text=True)
        if not re.search(r'\]\s+\.(text|rodata)\s+PROGBITS\s', sections):
            raise ValueError(f'runtime library has no code or data: {soname}')
        if dynamic(path)[0] != soname:
            raise ValueError(f'runtime SONAME mismatch: {soname}')
    return [{'url': url, 'urls': package_urls(url), 'sha256': checksum}
            for url, _, checksum in packages]


def bazel_sources(libraries, host_libraries, runtime_repository="chromium_platform_runtime",
                  headers_repository="chromium_platform_headers", host_runtime_repository=None):
    sources = '{source: "platform_runtime/" + name for name, source in runtime_files.items()}'
    host_files = []
    if host_runtime_repository:
        host_files = [f'    host_runtime_files = {{name: BAZEL_LIBRARIES.get(name, "@{host_runtime_repository}//:" + name) for name in SONAMES}}',
                      '    host_runtime_files.update({"lib" + name + ".chk": "@nss//:" + name + "_checksum" for name in ["freebl3", "freeblpriv3", "nssdbm3", "softokn3"]})']
        sources = 'select({"@platforms//cpu:aarch64": ' + sources + ', "//conditions:default": {source: "platform_runtime/" + name for name, source in host_runtime_files.items()}})'
    return '\n'.join([
        '"""Verified platform runtime libraries at Chromium build paths."""',
        'load(":public_dependency.bzl", "chromium_link_dependency")',
        'load(":python_action.bzl", "chromium_filegroup")',
        'load(":resource_copy.bzl", "chromium_resource_copy")',
        'SONAMES = ' + json.dumps(sorted(set(libraries) | set(NATIVE_LIBRARIES)), indent=4),
        'HOST_SONAMES = ' + json.dumps(sorted(set(host_libraries) | set(NATIVE_LIBRARIES)), indent=4),
        'BAZEL_LIBRARIES = ' + json.dumps(BAZEL_LIBRARIES, indent=4),
        '',
        'def native_platform_runtime():',
        '    chromium_link_dependency(',
        '        name = "platform_xshmfence_link",',
        f'        dependency = "@{headers_repository}//:xshmfence_shared",',
        '    )',
        f'    runtime_files = {{name: BAZEL_LIBRARIES.get(name, "@{runtime_repository}//:" + name) for name in SONAMES}}',
        '    runtime_files.update({',
        '        "lib" + name + ".chk": "@nss//:" + name + "_checksum"',
        '        for name in ["freebl3", "freeblpriv3", "nssdbm3", "softokn3"]',
        '    })',
        *host_files,
        '    chromium_resource_copy(',
        '        name = "platform_runtime_copies",',
        '        srcs = ' + sources + ',',
        '        outputs = {"lib/" + name: "platform_runtime/" + name for name in runtime_files},',
        '    )',
        '    chromium_filegroup(',
        '        name = "browser_platform_runtime",',
        '        srcs = {":lib/" + name: "out/bazel-import/lib/" + name for name in runtime_files},',
        '    )',
        '    chromium_filegroup(',
        '        name = "browser_host_platform_runtime",',
        '        srcs = {":lib/" + name: "out/bazel-import/lib/" + name for name in HOST_SONAMES},',
        '    )',
        '',
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sysroot', type=Path, required=True)
    parser.add_argument('--architecture', choices=('amd64', 'arm64'), default='amd64')
    parser.add_argument('--runtime-repository', default='chromium_platform_runtime')
    parser.add_argument('--headers-repository', default='chromium_platform_headers')
    parser.add_argument('--host-runtime-repository')
    parser.add_argument('--library', action='append', default=[])
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--download-dir', type=Path,
                        help='Download exact Debian packages and verify original library code')
    parser.add_argument('--output', type=Path, default=ROOT / 'native/platform_runtime.json')
    parser.add_argument('--bazel-output', type=Path,
                        help='Write the native runtime copy and logical-input providers')
    args = parser.parse_args()
    sysroot = args.sysroot.resolve()
    template = Path(__file__).resolve().parents[3] / 'build/platform_headers.BUILD.bazel'
    triple = 'aarch64-linux-gnu' if args.architecture == 'arm64' else 'x86_64-linux-gnu'
    system_libraries = set(SYSTEM_LIBRARIES)
    if args.architecture == 'arm64':
        system_libraries.remove('ld-linux-x86-64.so.2')
        system_libraries.add('ld-linux-aarch64.so.1')
    roots = []
    host_roots = []
    for call in ast.walk(ast.parse(template.read_text())):
        if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name):
            continue
        if call.func.id == 'cc_import':
            fields = {item.arg: ast.literal_eval(item.value) for item in call.keywords}
            if 'interface_library' in fields:
                path = sysroot / fields['interface_library'].replace('x86_64-linux-gnu', triple)
                roots.append(path)
                if not fields['name'].startswith('qt'):
                    host_roots.append(path)
    directories = [sysroot / part for part in [
        'usr/lib/' + triple, 'lib/' + triple,
        'usr/lib', 'lib', 'usr/lib/gcc/' + triple + '/10',
    ]]
    owners = {}
    controls = {}
    for control in (sysroot / 'debian').glob('*/DEBIAN/control'):
        fields = dict(line.split(': ', 1) for line in control.read_text().splitlines()
                      if ': ' in line and not line.startswith(' '))
        package = fields['Package']
        controls[package] = fields
        checksums = control.with_name('md5sums')
        if checksums.exists():
            for line in checksums.read_text().splitlines():
                checksum, path = line.split(maxsplit=1)
                owners[path] = (package, checksum)
    urls = {}
    package_list = args.source_root / ('build/linux/sysroot_scripts/generated_package_lists/bullseye.' + args.architecture)
    for url in package_list.read_text().splitlines():
        urls[unquote(url.rsplit('/', 1)[-1])] = url

    def resolve(name):
        for directory in directories:
            path = directory / name
            if path.is_file():
                return path
        raise FileNotFoundError(f'SDK runtime library absent: {name}')

    roots.extend(resolve(name) for name in args.library)
    pending = list(roots)
    libraries = {}
    while pending:
        path = pending.pop().resolve()
        relative = str(path.relative_to(sysroot))
        soname, needed = dynamic(path)
        if soname in system_libraries:
            continue
        if soname in libraries:
            if libraries[soname]['interface'] != relative:
                raise ValueError(f'conflicting SDK runtime library: {soname}')
            continue
        package, checksum = owners[relative]
        fields = controls[package]
        version = fields['Version'].split(':', 1)[-1]
        filename = f"{package}_{version}_{fields['Architecture']}.deb"
        libraries[soname] = {
            'interface': relative, 'needed': sorted(needed),
            'package': package, 'url': urls[filename], 'md5': checksum,
        }
        pending.extend(resolve(name) for name in needed if name not in system_libraries)
    host_libraries = set()
    pending = [dynamic(path)[0] for path in host_roots]
    while pending:
        soname = pending.pop()
        if soname in system_libraries or soname in host_libraries:
            continue
        host_libraries.add(soname)
        pending.extend(libraries[soname]['needed'])
    result = {
        'root_libraries': sorted({str(path.relative_to(sysroot)) for path in roots}),
        'system_libraries': sorted(system_libraries),
        'libraries': dict(sorted(libraries.items())),
        'host_libraries': sorted(host_libraries),
        'bazel_libraries': BAZEL_LIBRARIES,
    }
    if args.download_dir:
        result['packages'] = download_packages(libraries, args.download_dir.resolve())
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    if args.bazel_output:
        args.bazel_output.write_text(bazel_sources(libraries, host_libraries, args.runtime_repository, args.headers_repository, args.host_runtime_repository))
    print(f'{len(libraries)} library requirements; {len({row["package"] for row in libraries.values()})} runtime packages; SDK interfaces contain no executable code')


if __name__ == '__main__':
    main()
