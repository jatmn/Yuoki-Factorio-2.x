#!/usr/bin/env python3
"""Check release versions, build the installable ZIP and extract authored notes."""
import argparse
import json
from pathlib import Path
import re

from package import ROOT, pack, release_source
from validate_package import validate


def prepare(tag, output):
    if not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+', tag):
        raise ValueError('Release tag must be vMAJOR.MINOR.PATCH')
    version = tag[1:]
    if any(int(part) > 65535 for part in version.split('.')) or version == '0.0.0':
        raise ValueError('Release version is outside Factorio limits')
    info = json.loads(release_source('info.json').read_text())
    manifest = json.loads(release_source('.github/.release-please-manifest.json').read_text())
    if not (info['version'] == manifest.get('.') ==
            release_source('.github/version.txt').read_text().strip() == version):
        raise ValueError('Tag, info.json, Release Please manifest and version file must agree')
    if info['factorio_version'] != '2.1':
        raise ValueError('This release workflow targets Factorio 2.1')

    changelog = release_source('changelog.txt').read_text()
    sections = re.split(r'^-{99}\n', changelog, flags=re.MULTILINE)
    if sections[0].strip() or len(sections) < 2:
        raise ValueError('Changelog must begin with the Factorio 99-dash separator')
    section = sections[1].rstrip('\n')
    lines = section.splitlines()
    if not lines or lines[0] != f'Version: {version}':
        raise ValueError('Newest changelog section must match the release version')
    if any(line.startswith('Version:') for line in lines[1:]):
        raise ValueError('Newest changelog section contains another Version header; check separators')
    if not any(line.startswith('    - ') and line[6:].strip() for line in lines):
        raise ValueError('Release changelog must contain authored entries')
    # Preserve historical sections and the authors' wording. GitHub uses a text
    # block because Factorio indentation has a different meaning in Markdown.
    fence = '`' * max(3, max((len(m[0]) + 1 for m in re.finditer(r'`+', section)), default=3))
    notes = f'{fence}text\n{section}\n{fence}\n'
    output.mkdir(parents=True, exist_ok=True)
    archive = pack(output)
    validate(output)
    (output / 'release-notes.md').write_text(notes)
    return archive


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'build/dist')
    args = parser.parse_args()
    prepare(args.tag, args.output)
