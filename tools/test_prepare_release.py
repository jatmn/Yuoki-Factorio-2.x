#!/usr/bin/env python3
"""Exercise release preparation through its CLI and the real ZIP tools."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import textwrap
import unittest
import zipfile

from test_package import PackageSourceTests


class ReleaseTests(unittest.TestCase):
    git = PackageSourceTests.git

    def setUp(self):
        PackageSourceTests.setUp(self)
        shutil.copy(Path(__file__).with_name('prepare_release.py'), self.root / 'tools')
        info = json.loads((self.root / 'info.json').read_text())
        info.update(version='1.3.1', factorio_version='2.1', dependencies=['base >= 2.1.20'])
        (self.root / 'info.json').write_text(json.dumps(info))
        (self.root / '.github').mkdir()
        (self.root / '.github/.release-please-manifest.json').write_text('{".": "1.3.1"}\n')
        (self.root / '.github/version.txt').write_text('1.3.1\n')
        self.notes = 'Version: 1.3.1\nDate: 30. 10. 2026\n  Fixes:\n    - Restored graphics.\n'
        self.changelog = '-' * 99 + '\n' + self.notes + '-' * 99 + '\nVersion: 1.3.0\n  Changes:\n    - Old history.\n'
        (self.root / 'changelog.txt').write_text(self.changelog)
        self.git('add', '.')

    def prepare(self, tag='v1.3.1'):
        return subprocess.run([
            sys.executable, str(self.root / 'tools/prepare_release.py'),
            '--tag', tag, '--output', str(self.output),
        ], cwd=self.root, capture_output=True, text=True)

    def test_installable_zip_and_only_current_authored_notes(self):
        result = self.prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        with zipfile.ZipFile(self.output / 'Yuoki_1.3.1.zip') as archive:
            self.assertEqual(json.loads(archive.read('Yuoki_1.3.1/info.json'))['version'], '1.3.1')
            self.assertEqual(archive.read('Yuoki_1.3.1/changelog.txt').decode(), self.changelog)
            self.assertFalse(any('/.github/' in name or '/tools/' in name for name in archive.namelist()))
        notes = (self.output / 'release-notes.md').read_text()
        self.assertIn(self.notes, notes)
        self.assertNotIn('Old history', notes)
        before = (self.output / 'Yuoki_1.3.1.zip').read_bytes()
        self.assertEqual(self.prepare().returncode, 0)
        self.assertEqual((self.output / 'Yuoki_1.3.1.zip').read_bytes(), before)

    def test_version_disagreement_and_invalid_versions_stop_before_build(self):
        for tag in ('v1.3.2', 'v1.3.1-rc.1', 'v1.3.65536', '../bad', 'v0.0.0'):
            with self.subTest(tag=tag):
                self.assertNotEqual(self.prepare(tag).returncode, 0)
                self.assertEqual(list(self.output.iterdir()), [])
        for path, content in (
            ('.github/.release-please-manifest.json', '{}'),
            ('.github/version.txt', '1.3.0'),
            ('changelog.txt', self.changelog.replace('Version: 1.3.1', 'Version: 1.3.2')),
        ):
            with self.subTest(path=path):
                original = (self.root / path).read_text()
                (self.root / path).write_text(content)
                self.assertNotEqual(self.prepare().returncode, 0)
                self.assertEqual(list(self.output.iterdir()), [])
                (self.root / path).write_text(original)

    def test_next_release_uses_new_version_and_its_authored_section(self):
        info = json.loads((self.root / 'info.json').read_text())
        info['version'] = '1.3.2'
        (self.root / 'info.json').write_text(json.dumps(info))
        (self.root / '.github/.release-please-manifest.json').write_text('{".": "1.3.2"}')
        (self.root / '.github/version.txt').write_text('1.3.2')
        (self.root / 'changelog.txt').write_text(
            '-' * 99 + '\nVersion: 1.3.2\n  Fixes:\n    - Next fix.\n' + self.changelog)
        result = self.prepare('v1.3.2')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.output / 'Yuoki_1.3.2.zip').exists())
        self.assertNotIn('Restored graphics', (self.output / 'release-notes.md').read_text())

    def test_unpublished_draft_stops_normal_workflow_before_release_please(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    '.github/workflows/release-please.yml').read_text()
        # Execute the actual preflight shell with simulated GitHub API output.
        script = textwrap.dedent(workflow.split('run: |\n', 1)[1].split('\n\n', 1)[0])
        cli = self.workspace / 'gh'
        cli.write_text('#!/bin/sh\nprintf "%s" "$PENDING_DRAFT"\n')
        cli.chmod(0o755)
        for pending, expected in (('', 0), ('v1.3.1', 1)):
            with self.subTest(pending=pending):
                result = subprocess.run(
                    ['bash', '-e', '-o', 'pipefail', '-c', script], capture_output=True, text=True,
                    env={**os.environ, 'PATH': str(self.workspace) + os.pathsep + os.environ['PATH'],
                         'PENDING_DRAFT': pending, 'GH_REPO': 'fixture/fixture'},
                )
                self.assertEqual(result.returncode, expected, result.stderr)
                if pending:
                    self.assertIn('retry_tag: v1.3.1', result.stdout)


if __name__ == '__main__':
    unittest.main(defaultTest='ReleaseTests')
