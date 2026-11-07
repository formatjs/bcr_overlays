"""Compare cached browser payload bytes, excluding revision stamps."""

import argparse
import gzip
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tarfile
import tempfile
import urllib.request
import zlib

from tools.ci.buildbuddy_artifacts import (
    MAX_ARCHIVE_BYTES, api_request, artifact_uris, invocation_id,
)
from tools.ci.chromium import CONFIGURATION, PLATFORMS


def validate_stamp(data, revision, platform):
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:') as archive:
        members = archive.getmembers()
        if len(members) != 1 or members[0].name != 'artifact.json' or not members[0].isfile():
            raise ValueError('Expected one artifact stamp')
        metadata = json.load(archive.extractfile(members[0]))
    expected = {
        'schema_version': 1, 'platform': platform, 'revision': revision,
        'version': CONFIGURATION['version'], 'executable': PLATFORMS[platform]['executable'],
    }
    if metadata != expected:
        raise ValueError('Artifact stamp does not match requested build')


def payload_digest(source, expected_checksum, revision, platform):
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    stamp = bytearray()
    archive_hash, payload_hash = hashlib.sha256(), hashlib.sha256()
    archive_size = payload_size = prefix_size = 0
    while chunk := source.read(1024 * 1024):
        archive_size += len(chunk)
        if archive_size > MAX_ARCHIVE_BYTES:
            raise ValueError('Artifact exceeds size limit')
        archive_hash.update(chunk)
        if decoder.eof:
            payload_hash.update(chunk)
            payload_size += len(chunk)
            continue
        stamp.extend(decoder.decompress(chunk, 65537 - len(stamp)))
        prefix_size += len(chunk) - len(decoder.unused_data)
        if len(stamp) > 65536 or prefix_size > 1024 * 1024:
            raise ValueError('Artifact stamp exceeds size limit')
        if decoder.eof:
            validate_stamp(stamp, revision, platform)
            payload_hash.update(decoder.unused_data)
            payload_size += len(decoder.unused_data)
    if not decoder.eof or not payload_size:
        raise ValueError('Artifact is missing its cached payload')
    if archive_hash.hexdigest() != expected_checksum:
        raise ValueError('Artifact SHA256 mismatch')
    return {'sha256': payload_hash.hexdigest(), 'size_bytes': payload_size}


def payload_manifest(path):
    """Inspect the cached gzip member without extracting or executing files."""
    with path.open('rb') as raw:
        prefix = raw.read(1024 * 1024)
        decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
        decoder.decompress(prefix, 65537)
        if not decoder.eof:
            raise ValueError('Artifact stamp exceeds size limit')
        offset = len(prefix) - len(decoder.unused_data)
        raw.seek(offset)
        header = raw.read(10).hex()
        raw.seek(offset)
        digest, size = hashlib.sha256(), 0
        with gzip.GzipFile(fileobj=raw, mode='rb') as source:
            while chunk := source.read(1024 * 1024):
                size += len(chunk)
                if size > 32 * 1024 * 1024 * 1024:
                    raise ValueError('Uncompressed payload exceeds 32 GiB')
                digest.update(chunk)
        raw.seek(offset)
        members = []
        with gzip.GzipFile(fileobj=raw, mode='rb') as source, tarfile.open(fileobj=source, mode='r|') as archive:
            for member in archive:
                if len(members) >= 100000:
                    raise ValueError('Payload contains too many members')
                row = {key: getattr(member, key) for key in (
                    'name', 'size', 'mode', 'uid', 'gid', 'mtime', 'uname', 'gname', 'linkname', 'pax_headers')}
                row['type'] = member.type.decode('latin1')
                if member.isfile():
                    with archive.extractfile(member) as content:
                        row['sha256'] = hashlib.file_digest(content, 'sha256').hexdigest()
                members.append(row)
    return {'tar_sha256': digest.hexdigest(), 'tar_size_bytes': size,
            'gzip_header_hex': header, 'members': members}


def build_urls(revision, platforms=PLATFORMS, kind='browser'):
    repository = os.environ.get('GITHUB_REPOSITORY', 'formatjs/chromium')
    request = urllib.request.Request(
        f'https://api.github.com/repos/{repository}/commits/{revision}/status?per_page=100',
        headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN']})
    with urllib.request.urlopen(request, timeout=60) as response:
        statuses = json.load(response)['statuses']
    by_context = {}
    for status in statuses:
        by_context.setdefault(status['context'], status)
    urls = {}
    prefix = 'Chromium cold build ' if kind == 'cold-browser' else 'Chromium '
    for platform in platforms:
        status = by_context.get(prefix + platform, {})
        if status.get('state') != 'success':
            raise ValueError('Browser build has not passed: ' + platform)
        urls[platform] = status['target_url']
    return urls


def digest_artifact(url, revision, platform, kind='browser', *, diagnose_members=False):
    key = os.environ['BUILDBUDDY_API_KEY']
    with api_request('GetInvocation', {
            'selector': {'invocation_id': invocation_id(url)}, 'include_artifacts': True,
    }, key) as response:
        uris = artifact_uris(json.load(response), revision, platform, kind=kind)
    name = 'chromium-' + platform + '.tar.gz'
    with api_request('GetFile', {'uri': uris[name + '.sha256']}, key) as response:
        expected = response.read(66).decode().strip()
    if not re.fullmatch(r'[0-9a-f]{64}', expected):
        raise ValueError('Invalid artifact checksum')
    with api_request('GetFile', {'uri': uris[name]}, key) as response:
        if not diagnose_members:
            return payload_digest(response, expected, revision, platform)
        with tempfile.TemporaryDirectory(prefix='chromium-payload-diff-') as temporary:
            path = Path(temporary) / name
            size = 0
            with path.open('wb') as output:
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_ARCHIVE_BYTES:
                        raise ValueError('Artifact exceeds size limit')
                    output.write(chunk)
            with path.open('rb') as source:
                result = payload_digest(source, expected, revision, platform)
            result['manifest'] = payload_manifest(path)
            return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--platform', choices=sorted(PLATFORMS))
    parser.add_argument('--revision-kind', choices=['browser', 'cold-browser'], default='browser')
    parser.add_argument('--diagnose-members', action='store_true')
    args = parser.parse_args()
    if any(not re.fullmatch(r'[0-9a-f]{40}', value) for value in (args.baseline, args.revision)):
        parser.error('Expected full source commit SHAs')
    platforms = [args.platform] if args.platform else list(PLATFORMS)
    baseline_key = (args.baseline, 'browser')
    revision_key = (args.revision, args.revision_kind)
    urls_by_build = {key: build_urls(key[0], platforms, key[1]) for key in dict.fromkeys((baseline_key, revision_key))}
    result = {'baseline': args.baseline, 'revision': args.revision,
              'revision_kind': args.revision_kind, 'platforms': {}}
    args.directory.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            (platform, *key): executor.submit(digest_artifact, urls[platform], key[0], platform, key[1],
                                            **({'diagnose_members': True} if args.diagnose_members else {}))
            for platform in platforms
            for key, urls in urls_by_build.items()
        }
        for platform in platforms:
            baseline = futures[platform, *baseline_key].result()
            current = futures[platform, *revision_key].result()
            result['platforms'][platform] = {
                'baseline': baseline, 'current': current, 'payload_bytes_match': baseline == current,
            }
            print(platform + ': payload bytes ' + ('match' if baseline == current else 'changed'), flush=True)
            (args.directory / 'payload-comparison.json').write_text(json.dumps(result, indent=2) + '\n')
    if not all(item['payload_bytes_match'] for item in result['platforms'].values()):
        raise ValueError('Browser payload bytes changed; inspect code and debug differences')


if __name__ == '__main__':
    main()
