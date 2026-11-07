"""Browser helpers may inherit output handles after the browser exits."""
import os
from pathlib import Path
import signal
import sys
import tempfile
import unittest

from overlays.chromium.tools.check_browser import run


class BrowserProcessTest(unittest.TestCase):
    @unittest.skipUnless(os.name == 'posix', 'POSIX inherited output handles')
    def test_browser_exit_does_not_wait_for_helper_output_handles(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            program = '''
import subprocess, sys
from pathlib import Path
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(3)'])
Path('helper.pid').write_text(str(child.pid))
print('rendered \\u00e9', flush=True)
'''
            try:
                self.assertEqual(run(sys.executable, ['-c', program], dict(os.environ), directory, 1),
                                 'rendered é\n')
            finally:
                if (directory / 'helper.pid').exists():
                    try:
                        os.kill(int((directory / 'helper.pid').read_text()), signal.SIGTERM)
                    except ProcessLookupError:
                        pass

    def test_browser_failure_keeps_stderr(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(RuntimeError, 'browser exited 7: native failure'):
                run(sys.executable, ['-c', 'import sys; sys.stderr.write("native failure"); sys.exit(7)'],
                    dict(os.environ), Path(temporary), 2)

    def test_live_browser_still_times_out(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(RuntimeError, 'browser timed out after 0.1s'):
                run(sys.executable, ['-c', 'import time; time.sleep(3)'],
                    dict(os.environ), Path(temporary), 0.1)
