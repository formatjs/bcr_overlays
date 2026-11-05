# SPDX-License-Identifier: Apache-2.0
"""Exercise emitted WebUI modules and Chromium's patched TypeScript compiler."""

import gzip
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from python.runfiles import runfiles
from grit.format import data_pack


class WebuiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        resolver = runfiles.Create()
        (cls.node, cls.typescript, cls.base, cls.assert_js, cls.promise_js,
         cls.downloads_header, cls.downloads_pack, cls.downloads_js,
         cls.perfetto_js, cls.wire_js) = (
            Path(resolver.Rlocation(path)).resolve() for path in sys.argv[1:])

    def test_perfetto_wire_contract(self):
        program = r'''
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {SourceTextModule} from 'node:vm';
const schema = new SourceTextModule(readFileSync(process.argv[1], 'utf8'));
const wire = new SourceTextModule(readFileSync(process.argv[2], 'utf8'));
await schema.link(specifier => {
  assert.equal(specifier, '/@bufbuild/protobuf/wire/index.js');
  return wire;
});
await schema.evaluate();
const {TraceConfig} = schema.namespace;
const golden = Uint8Array.from([0x0a, 0x02, 0x08, 0x40, 0x18, 0xe8, 0x07]);
const config = TraceConfig.fromPartial({buffers: [{sizeKb: 64}], durationMs: 1000});
assert.deepEqual(TraceConfig.encode(config).finish(), golden);
const decoded = TraceConfig.decode(golden);
assert.equal(decoded.buffers.length, 1);
assert.equal(decoded.buffers[0].sizeKb, 64);
assert.equal(decoded.durationMs, 1000);
const extended = Uint8Array.from([...golden, 0xa0, 0x06, 0x07]);
assert.equal(TraceConfig.decode(extended).durationMs, 1000);
assert.throws(() => TraceConfig.decode(Uint8Array.from([0x0a, 0x02, 0x08])));
'''
        subprocess.run([self.node, '--experimental-vm-modules', '--input-type=module',
                        '-e', program, self.perfetto_js, self.wire_js], check=True)

    def test_downloads_page_pack(self):
        ids = {name: int(value) for name, value in re.findall(
            r'^#define\s+(\w+)\s+(\d+)\s*$', self.downloads_header.read_text(), re.M)}
        resources = data_pack.ReadDataPack(str(self.downloads_pack)).resources
        html = gzip.decompress(resources[ids['IDR_DOWNLOADS_DOWNLOADS_HTML']])
        javascript = gzip.decompress(resources[ids['IDR_DOWNLOADS_DOWNLOADS_ROLLUP_JS']])
        self.assertEqual(javascript, self.downloads_js.read_bytes())
        scripts = []

        class Page(HTMLParser):
            def handle_starttag(self, tag, attrs):
                attributes = dict(attrs)
                if tag == 'script' and attributes.get('type') == 'module':
                    scripts.append(attributes.get('src'))

        Page().feed(html.decode())
        self.assertIn('downloads.js', scripts)
        self.assertIn(b'downloads-manager', javascript)
        subprocess.run([self.node, '--check', '--input-type=module'],
                       input=javascript, check=True)

    def test_emitted_modules(self):
        program = r'''
import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
const load = async path => import('data:text/javascript;base64,' +
    readFileSync(path).toString('base64'));
const checks = await load(process.argv[1]);
const {PromiseResolver} = await load(process.argv[2]);
checks.assert(true);
assert.throws(() => checks.assert(false, 'webui'), /Assertion failed: webui/);
const success = new PromiseResolver();
assert.equal(success.isFulfilled, false);
success.resolve(42);
assert.equal(await success.promise, 42);
assert.equal(success.isFulfilled, true);
const failure = new PromiseResolver();
const rejected = assert.rejects(failure.promise, /webui failure/);
failure.reject(new Error('webui failure'));
await rejected;
assert.equal(failure.isFulfilled, true);
'''
        subprocess.run([self.node, '--input-type=module', '-e', program,
                        self.assert_js, self.promise_js], check=True)

    def test_trusted_html_and_type_error_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tools = root / 'tools/typescript'
            tools.mkdir(parents=True)
            shutil.copy2(self.base, tools / 'tsconfig_base.json')
            modules = root / 'third_party/node/node_modules'
            modules.parent.mkdir(parents=True)
            modules.symlink_to(self.typescript.parent.parent)
            config = root / 'tsconfig.json'
            config.write_text(json.dumps({
                'extends': './tools/typescript/tsconfig_base.json',
                'compilerOptions': {'outDir': './output'},
                'files': ['input.ts'],
            }))
            source = root / 'input.ts'
            source.write_text('''
const html = window.trustedTypes!.createPolicy('webui', {
  createHTML: (text: string) => text,
}).createHTML('<b>webui</b>');
document.createElement('div').innerHTML = html;
export const value: number = 42;
''')
            command = [self.node, modules / 'typescript/bin/tsc',
                       '--project', config, '--pretty', 'false']
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            emitted = root / 'output/input.js'
            self.assertIn('export const value = 42', emitted.read_text())
            emitted.unlink()
            source.write_text("export const value: number = 'wrong';\n")
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('TS2322', result.stdout + result.stderr)
            self.assertFalse(emitted.exists(), 'Type error emitted executable JS')


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]])
