#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check the assembled browser version and headless renderer."""

import argparse
import ctypes
from contextlib import contextmanager
from functools import partial
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import threading


class PageResult(HTMLParser):
    def __init__(self):
        super().__init__()
        self.collect = False
        self.value = ''

    def handle_starttag(self, tag, attrs):
        if tag == 'output' and dict(attrs).get('id') == 'result':
            self.collect = True

    def handle_endtag(self, tag):
        if tag == 'output':
            self.collect = False

    def handle_data(self, data):
        if self.collect:
            self.value += data


def windows_version(browser):
    version = ctypes.WinDLL('version.dll', use_last_error=True)
    integer = ctypes.c_uint32
    version.GetFileVersionInfoSizeW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(integer)]
    version.GetFileVersionInfoSizeW.restype = integer
    version.GetFileVersionInfoW.argtypes = [ctypes.c_wchar_p, integer, integer, ctypes.c_void_p]
    version.GetFileVersionInfoW.restype = ctypes.c_int
    version.VerQueryValueW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p,
                                     ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(integer)]
    version.VerQueryValueW.restype = ctypes.c_int
    size = version.GetFileVersionInfoSizeW(str(browser), ctypes.byref(integer()))
    if not size:
        raise ctypes.WinError()
    data = ctypes.create_string_buffer(size)
    if not version.GetFileVersionInfoW(str(browser), 0, size, data):
        raise ctypes.WinError()

    def query(key):
        pointer, length = ctypes.c_void_p(), integer()
        if not version.VerQueryValueW(data, key, ctypes.byref(pointer), ctypes.byref(length)):
            raise ctypes.WinError()
        return pointer, length.value

    pointer, length = query('\\')
    if length < 52:
        raise ValueError('incomplete Windows version resource')
    fields = struct.unpack('<13I', ctypes.string_at(pointer, 52))
    if fields[0] != 0xFEEF04BD:
        raise ValueError('invalid Windows version resource')
    major, minor, build, patch = fields[4] >> 16, fields[4] & 0xffff, fields[5] >> 16, fields[5] & 0xffff
    pointer, length = query('\\VarFileInfo\\Translation')
    if length < 4:
        raise ValueError('missing Windows version translation')
    language, codepage = struct.unpack('<HH', ctypes.string_at(pointer, 4))
    pointer, length = query(f'\\StringFileInfo\\{language:04x}{codepage:04x}\\ProductName')
    product = ctypes.string_at(pointer, length * 2).decode('utf-16-le').rstrip('\0')
    return f'{product} {major}.{minor}.{build}.{patch}'


def sample_browser(process, directory):
    if sys.platform != 'darwin':
        return ''
    sample = directory / 'browser-timeout.sample.txt'
    try:
        subprocess.run(['/usr/bin/sample', str(process.pid), '1', '1', '-file', str(sample)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
                       check=True, timeout=10)
        return '\nmacOS process sample:\n' + sample.read_text(errors='replace')[:24000]
    except (OSError, subprocess.SubprocessError) as error:
        return '\nmacOS process sample unavailable: ' + str(error)


def run(browser, arguments, environment, directory, timeout):
    # Helpers can retain inherited pipes after the browser has exited.
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        timed_out = None
        diagnostic = ''
        with subprocess.Popen([str(browser), *arguments], cwd=directory, env=environment,
                              stdout=stdout, stderr=stderr) as process:
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired as error:
                diagnostic = sample_browser(process, directory)
                process.kill()
                process.wait(timeout=5)
                timed_out = error
        stdout.seek(0)
        stderr.seek(0)
        output = stdout.read().decode('utf-8', errors='replace')
        errors = stderr.read().decode('utf-8', errors='replace')
        if timed_out is not None:
            captured = [name + ': ' + value[-8000:]
                        for name, value in [('stdout', output), ('stderr', errors)] if value]
            raise RuntimeError(f'browser timed out after {timeout}s: ' + '\n'.join(captured)
                               + diagnostic) from timed_out
        if process.returncode:
            raise RuntimeError(f'browser exited {process.returncode}: {errors[-8000:]}')
        return output


def browser_version(browser, environment, directory, timeout):
    # Windows Chromium does not implement --version.
    if sys.platform == 'win32':
        return windows_version(browser)
    return run(browser, ['--version'], environment, directory, timeout).strip()


@contextmanager
def serve_page(directory):
    requested = set()

    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            requested.add(self.path)
            super().do_GET()

        def log_message(self, format, *args):
            pass

    with ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(directory))) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f'http://127.0.0.1:{server.server_port}/page.html', requested
        finally:
            server.shutdown()
            thread.join()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path, help='Assembled browser bundle containing chrome')
    parser.add_argument('--expected-version', default='142.0.7444.59')
    parser.add_argument('--executable', default='chrome', help='Executable path relative to the bundle')
    parser.add_argument('--timeout', type=float, default=60)
    parser.add_argument('--no-sandbox', action='store_true', help='For hosts without Chromium sandbox support')
    args = parser.parse_args()
    browser = args.directory.resolve() / args.executable
    if not browser.is_file() or not os.access(browser, os.X_OK):
        raise ValueError(f'missing browser executable: {browser}')
    environment = dict(os.environ)
    environment.pop('LD_LIBRARY_PATH', None)
    with tempfile.TemporaryDirectory(prefix='chromium-browser-check.') as temporary:
        directory = Path(temporary)
        version = browser_version(browser, environment, directory, args.timeout)
        if not re.fullmatch(r'Chromium ' + re.escape(args.expected_version) + r'(?:\s.*)?', version):
            raise ValueError(f'unexpected browser version: {version!r}')
        (directory / 'page.html').write_text(
            '<!doctype html><meta charset="utf-8"><title>Native Bazel Chromium</title>'
            '<link rel="stylesheet" href="page.css">'
            '<output id="result">pending</output><div id="layout"></div>'
            '<script defer src="page.js"></script>', encoding='utf-8',
        )
        (directory / 'page.css').write_text('#layout { width: 123px; }\n')
        (directory / 'page.js').write_text('''
Promise.resolve().then(() => {
  document.getElementById('result').textContent = [
    'e\\u0301'.normalize('NFC'),
    new Intl.NumberFormat('fr-FR', {useGrouping: false}).format(1234.5),
    (() => 6 * 7)(),
    document.getElementById('layout').getBoundingClientRect().width,
  ].join('|');
});
''', encoding='utf-8')
        arguments = [
            '--headless', '--disable-gpu', '--no-first-run', '--enable-logging=stderr',
            '--no-default-browser-check', '--disable-background-networking',
            '--user-data-dir=' + str(directory / 'profile'),
            '--dump-dom',
        ]
        if sys.platform == 'darwin':
            arguments.append('--vmodule=keep_alive_registry=1')
        if args.no_sandbox:
            arguments.insert(0, '--no-sandbox')
        page = PageResult()
        with serve_page(directory) as (url, requested):
            page.feed(run(browser, [*arguments, url], environment, directory, args.timeout))
        if not {'/page.html', '/page.js', '/page.css'}.issubset(requested):
            raise ValueError(f'headless HTTP resources missing: {sorted(requested)!r}')
        if page.value != 'é|1234,5|42|123':
            raise ValueError(f'headless page failed: {page.value!r}')
    print(version)
    print('Headless HTTP page: external JavaScript/CSS, Unicode, Intl and layout passed')


if __name__ == '__main__':
    main()
