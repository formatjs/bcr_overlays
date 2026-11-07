"""Require every generated binding to match, including the complete file set."""

import hashlib
import json
from pathlib import Path
import sys


def compare(entries):
    rows = []
    names = set()
    for entry in entries:
        if entry['name'] in names:
            raise ValueError('Duplicate binding output')
        names.add(entry['name'])
        digests = []
        for key in ('baseline', 'candidate'):
            with Path(entry[key]).open('rb') as source:
                digests.append(hashlib.file_digest(source, 'sha256').hexdigest())
        if digests[0] != digests[1]:
            raise ValueError('Binding bytes differ: ' + entry['name'])
        rows.append({'name': entry['name'], 'sha256': digests[0]})
    if not rows:
        raise ValueError('No binding outputs')
    return {'output_count': len(rows), 'all_bytes_match': True, 'outputs': rows}


if __name__ == '__main__':
    result = compare(json.loads(Path(sys.argv[1]).read_text()))
    Path(sys.argv[2]).write_text(json.dumps(result, indent=2) + '\n')
