#!/usr/bin/env python3
"""Run the native Chromium X11 test against a private Xvfb server."""
import argparse
import os
from pathlib import Path
import select
import shutil
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bazel', default='bazel')
    parser.add_argument('--output-user-root')
    parser.add_argument('--xvfb', default=shutil.which('Xvfb'))
    parser.add_argument('bazel_args', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.xvfb:
        parser.error('Xvfb is required for this integration test')
    with tempfile.TemporaryDirectory(prefix='chromium-x11-test-') as directory:
        log_path = Path(directory) / 'server.log'
        read_fd, write_fd = os.pipe()
        server = None
        try:
            with log_path.open('w') as log:
                server = subprocess.Popen(
                    [args.xvfb, '-displayfd', str(write_fd), '-nolisten', 'tcp',
                     '-noreset', '-screen', '0', '640x480x24'],
                    pass_fds=(write_fd,), stdout=log, stderr=subprocess.STDOUT)
            os.close(write_fd)
            write_fd = -1
            if not select.select([read_fd], [], [], 20)[0]:
                raise RuntimeError('Xvfb readiness timed out: ' + log_path.read_text())
            display = os.read(read_fd, 64).decode().strip()
            if not display.isdecimal():
                raise RuntimeError('Xvfb failed: ' + log_path.read_text())
            command = [args.bazel, '--batch']
            if args.output_user_root:
                command.append('--output_user_root=' + args.output_user_root)
            extra = args.bazel_args
            if extra[:1] == ['--']:
                extra = extra[1:]
            command += ['test', '//:x11_runtime_test', '--cache_test_results=no',
                        '--test_arg=--x11-display=:' + display, *extra]
            return subprocess.run(command, cwd=Path(__file__).resolve().parents[1]).returncode
        finally:
            os.close(read_fd)
            if write_fd >= 0:
                os.close(write_fd)
            if server is not None and server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()


if __name__ == '__main__':
    raise SystemExit(main())
