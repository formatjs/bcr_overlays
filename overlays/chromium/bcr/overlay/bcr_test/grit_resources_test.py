import re
import sys
from pathlib import Path

from grit.format import data_pack
from python.runfiles import runfiles


def main():
    resolver = runfiles.Create()
    paths = [Path(resolver.Rlocation(path)) for path in sys.argv[1:]]
    headers = []
    packs = []
    allocated = set()
    for index in range(5):
        names = dict(re.findall(r'^#define\s+(\w+)\s+(\d+)\s*$', paths[index].read_text(), re.M))
        names = {name: int(value) for name, value in names.items()}
        english = data_pack.ReadDataPack(str(paths[5 + index * 2]))
        french = data_pack.ReadDataPack(str(paths[6 + index * 2]))
        identifiers = set(english.resources)
        assert identifiers and identifiers == set(french.resources)
        assert identifiers <= set(names.values())
        assert not allocated.intersection(identifiers), 'resource ID ranges overlap'
        allocated.update(identifiers)
        headers.append(names)
        packs.append((english, french))
    cancel = headers[0]['IDS_APP_CANCEL']

    def text(pack, identifier):
        encoding = {data_pack.UTF8: 'utf-8', data_pack.UTF16: 'utf-16-le'}[pack.encoding]
        return pack.resources[identifier].decode(encoding)

    assert text(packs[0][0], cancel) == 'Cancel'
    assert text(packs[0][1], cancel) == 'Annuler'
    gendered = data_pack.ReadDataPack(str(paths[15]))
    french = packs[0][1]
    assert set(gendered.resources) <= set(french.resources)
    assert all(value != french.resources[key] for key, value in gendered.resources.items())
    selected = gendered if cancel in gendered.resources else french
    assert text(selected, cancel) == 'Annuler'


if __name__ == '__main__':
    main()
