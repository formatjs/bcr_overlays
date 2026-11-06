import importlib.util
from pathlib import Path
import tempfile
import unittest


script = Path(__file__).resolve().parents[1] / 'overlays/chromium/bcr/overlay/native/grit_resources.py'
spec = importlib.util.spec_from_file_location('grit_resources', script)
resources = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resources)


class GRITResourceTest(unittest.TestCase):
    def test_distinct_action_directories_produce_identical_utf8_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            outputs = []
            for name in ['action-one', 'action-two']:
                root = Path(directory) / name
                build = root / 'out/bazel-import'
                build.mkdir(parents=True)
                output = build / 'resources.rc'
                text = f'IDC_MAIN CURSOR "{root}/ui/resources/main.cur"\n1 L"你好"\n'
                output.write_bytes(text.encode('utf-16'))
                resources.normalize_resource(output, root, build)
                outputs.append(output.read_bytes())
            self.assertEqual(outputs[0], outputs[1])
            self.assertEqual(outputs[0].decode('utf-8'),
                             'IDC_MAIN CURSOR "../../ui/resources/main.cur"\n1 L"你好"\n')
