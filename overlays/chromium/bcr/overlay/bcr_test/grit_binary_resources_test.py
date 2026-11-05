import gzip
import json
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

from grit import constants
from grit.format import data_pack
from python.runfiles import runfiles


def main():
    resolver = runfiles.Create()
    paths = [Path(resolver.Rlocation(path)) for path in sys.argv[1:]]

    def header(path):
        return {name: int(value) for name, value in re.findall(
            r'^#define\s+(\w+)\s+(\d+)\s*$', path.read_text(), re.M)}

    def decode(payload):
        assert payload.startswith(constants.BROTLI_CONST)
        offset = len(constants.BROTLI_CONST)
        size = int.from_bytes(payload[offset:offset + 6], 'little')
        compressed = payload[offset + 6:]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'resource.br'
            source.write_bytes(compressed)
            result = subprocess.run([str(paths[0]), str(source), str(size)], check=True, capture_output=True)
            assert len(result.stdout) == size
            source.write_bytes(compressed[:-2])
            rejected = subprocess.run([str(paths[0]), str(source), str(size)], capture_output=True)
            assert rejected.returncode != 0, 'legacy decoder accepted truncated stream'
            return result.stdout

    glic_ids = header(paths[1])
    glic = data_pack.ReadDataPack(str(paths[2])).resources
    for name, source in [('IDR_GLIC_LOGO', paths[3]), ('IDR_GLIC_BORDER_SHADER', paths[4])]:
        assert decode(glic[glic_ids[name]]) == source.read_bytes()
    assert glic[glic_ids['IDR_GLIC_SHARE_IMAGE_ICON']] == paths[5].read_bytes()
    actor_ids = header(paths[6])
    actor = data_pack.ReadDataPack(str(paths[7])).resources
    framed = actor[actor_ids['IDR_ACTOR_TAB_INDICATOR_SPINNER']]
    assert framed.startswith(b'LOTTIE')
    animation = decode(framed[6:])
    assert json.loads(animation) == json.loads(paths[8].read_bytes())
    descriptor_ids = header(paths[9])
    descriptors = data_pack.ReadDataPack(str(paths[10])).resources
    assert gzip.decompress(descriptors[descriptor_ids['chrome_track_event_descriptor']]) == paths[11].read_bytes()
    for path in paths[12:]:
        images = data_pack.ReadDataPack(str(path)).resources
        pngs = [value for value in images.values() if value.startswith(b'\x89PNG\r\n\x1a\n')]
        assert pngs, f'no PNG resources in {path}'
        assert all(width > 0 and height > 0 for width, height in
                   (struct.unpack('>II', value[16:24]) for value in pngs))


if __name__ == '__main__':
    main()
