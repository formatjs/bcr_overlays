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


def build_urls(revision):
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
    for platform in PLATFORMS:
        status = by_context.get('Chromium ' + platform, {})
        if status.get('state') != 'success':
            raise ValueError('Browser build has not passed: ' + platform)
        urls[platform] = status['target_url']
    return urls


def digest_artifact(url, revision, platform):
    key = os.environ['BUILDBUDDY_API_KEY']
    with api_request('GetInvocation', {
            'selector': {'invocation_id': invocation_id(url)}, 'include_artifacts': True,
    }, key) as response:
        uris = artifact_uris(json.load(response), revision, platform)
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
    args = parser.parse_args()
    if any(not re.fullmatch(r'[0-9a-f]{40}', value) for value in (args.baseline, args.revision)):
        parser.error('Expected full source commit SHAs')
    baseline_urls = build_urls(args.baseline)
    revision_urls = baseline_urls if args.revision == args.baseline else build_urls(args.revision)
    urls_by_revision = {args.baseline: baseline_urls, args.revision: revision_urls}
    result = {'baseline': args.baseline, 'revision': args.revision, 'platforms': {}}
    args.directory.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            (platform, revision): executor.submit(digest_artifact, urls[platform], revision, platform)
            for platform in PLATFORMS
            for revision, urls in urls_by_revision.items()
        }
        for platform in PLATFORMS:
            baseline = futures[platform, args.baseline].result()
            current = futures[platform, args.revision].result()
            result['platforms'][platform] = {
                'baseline': baseline, 'current': current, 'payload_bytes_match': baseline == current,
            }
            print(platform + ': payload bytes ' + ('match' if baseline == current else 'changed'), flush=True)
            (args.directory / 'payload-comparison.json').write_text(json.dumps(result, indent=2) + '\n')
    if not all(item['payload_bytes_match'] for item in result['platforms'].values()):
        raise ValueError('Browser payload bytes changed; inspect code and debug differences')


if __name__ == '__main__':
    main()
