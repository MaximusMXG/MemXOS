#!/usr/bin/env python3
"""Download and authenticate the pinned Kubuntu base image."""
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

BASE = 'https://cdimage.ubuntu.com/kubuntu/releases/26.04/release/'
FILENAME = 'kubuntu-26.04.1-desktop-amd64.iso'
FINGERPRINT = '843938DF228D22F7B3742BC0D94AA3F0EFE21092'


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def fetch(url, path):
    with urllib.request.urlopen(url, timeout=90) as response, path.open('wb') as stream:
        shutil.copyfileobj(response, stream)


def verified_checksum(directory):
    directory.mkdir(parents=True, exist_ok=True)
    for name in ('SHA256SUMS', 'SHA256SUMS.gpg'):
        fetch(BASE + name, directory / name)
    with tempfile.TemporaryDirectory(prefix='memex-gpg-') as td:
        key = Path(td) / 'ubuntu.asc'
        fetch('https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x' + FINGERPRINT, key)
        subprocess.run(['gpg', '--homedir', td, '--batch', '--import', str(key)], check=True, capture_output=True)
        result = subprocess.run(['gpg', '--homedir', td, '--batch', '--status-fd', '1', '--verify',
                                 str(directory / 'SHA256SUMS.gpg'), str(directory / 'SHA256SUMS')],
                                capture_output=True, text=True, check=True)
        if '[GNUPG:] VALIDSIG ' + FINGERPRINT + ' ' not in result.stdout:
            raise RuntimeError('Checksum signature is not from the pinned Ubuntu CD-image signing key.')
    matches = [line.split()[0] for line in (directory / 'SHA256SUMS').read_text().splitlines()
               if line.split()[-1].lstrip('*') == FILENAME]
    if len(matches) != 1:
        raise RuntimeError('Pinned Kubuntu image is absent from the signed checksum list.')
    return matches[0]


def verify(path, directory):
    expected = verified_checksum(directory)
    if sha256(path) != expected:
        raise RuntimeError('Kubuntu ISO checksum does not match its authenticated release checksum.')
    return expected


def download(directory):
    expected = verified_checksum(directory)
    image = directory / FILENAME
    if not image.exists():
        partial = image.with_suffix('.iso.partial')
        print('Downloading ' + FILENAME, flush=True)
        fetch(BASE + FILENAME, partial)
        if sha256(partial) != expected:
            raise RuntimeError('Downloaded ISO checksum mismatch; partial file retained for inspection.')
        partial.rename(image)
    if sha256(image) != expected:
        raise RuntimeError('Cached ISO checksum mismatch.')
    return image


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache', type=Path, default=Path(__file__).parent / 'cache')
    parser.add_argument('--verify-only', type=Path)
    args = parser.parse_args()
    if args.verify_only:
        print(verify(args.verify_only, args.cache))
    else:
        print(download(args.cache))
