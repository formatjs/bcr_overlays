"""Compare cached browser payload bytes, excluding revision stamps."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tarfile
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


def digest_artifact(url, revision, platform, kind='browser'):
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
        return payload_digest(response, expected, revision, platform)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--platform', choices=sorted(PLATFORMS))
    parser.add_argument('--revision-kind', choices=['browser', 'cold-browser'], default='browser')
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
            (platform, *key): executor.submit(digest_artifact, urls[platform], key[0], platform, key[1])
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
