#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check the assembled browser version and headless renderer."""

import argparse
from contextlib import contextmanager
from functools import partial
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import re
import subprocess
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


def run(browser, arguments, environment, directory, timeout):
    result = subprocess.run(
        [str(browser), *arguments], cwd=directory, env=environment,
        text=True, encoding='utf-8', capture_output=True, timeout=timeout,
    )
    if result.returncode:
        raise RuntimeError(f'browser exited {result.returncode}: {result.stderr[-2000:]}')
    return result.stdout


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
        version = run(browser, ['--version'], environment, directory, args.timeout).strip()
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
            '--headless', '--disable-gpu', '--no-first-run',
            '--no-default-browser-check', '--disable-background-networking',
            '--user-data-dir=' + str(directory / 'profile'),
            '--dump-dom',
        ]
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
