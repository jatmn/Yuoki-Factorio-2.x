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
        self.assertEqual(
            (self.output / 'release-notes.md').read_text(),
            '```text\nVersion: 1.3.2\n  Fixes:\n    - Next fix.\n```\n',
        )

    def test_placeholder_notes_stop_before_build(self):
        for entry in ('', '   ', '\t'):
            with self.subTest(entry=entry):
                (self.root / 'changelog.txt').write_text(
                    self.changelog.replace('Restored graphics.', entry))
                result = self.prepare()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('must contain authored entries', result.stderr)
                self.assertEqual(list(self.output.iterdir()), [])

    def test_repository_release_inputs_preserve_release_contract(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / '.github/release-please-config.json').read_text())
        self.assertIs(config['draft-pull-request'], True)
        self.assertIs(config['draft'], True)
        # Exclude all history through the completed 1.3.0 release merge (#19).
        self.assertEqual(config['bootstrap-sha'], '50ea38b9703a13e8644c3bcfe6e400b3bf2b4a5c')
        self.assertEqual(set(config['packages']), {'.'})
        package = config['packages']['.']
        self.assertEqual(package['release-type'], 'simple')
        self.assertEqual(package['initial-version'], '1.3.1')
        self.assertIs(package['include-component-in-tag'], False)
        self.assertIs(package['skip-changelog'], True)
        self.assertEqual(package['version-file'], '.github/version.txt')
        self.assertIn({'type': 'json', 'path': 'info.json', 'jsonpath': '$.version'},
                      package['extra-files'])
        self.assertNotIn('release-as', config)
        self.assertNotIn('release-as', package)
        manifest = json.loads((root / '.github/.release-please-manifest.json').read_text())
        self.assertIsInstance(manifest, dict)
        self.assertIn(set(manifest), (set(), {'.'}))
        version = (root / '.github/version.txt').read_text().strip()
        self.assertEqual(version, json.loads((root / 'info.json').read_text())['version'])
        # Manifest can be empty for bootstrap, or older during abandonment.
        for value in [version, *manifest.values()]:
            self.assertRegex(value, r'^[0-9]+\.[0-9]+\.[0-9]+$')
            self.assertNotEqual(value, '0.0.0')
            self.assertTrue(all(int(part) <= 65535 for part in value.split('.')))
        if manifest:
            self.assertLessEqual(tuple(map(int, manifest['.'].split('.'))),
                                 tuple(map(int, version.split('.'))))

    def test_unpublished_draft_stops_normal_workflow_before_release_please(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    '.github/workflows/release-please.yml').read_text()
        # Execute the actual preflight shell with simulated GitHub API output.
        script = textwrap.dedent(workflow.split('run: |\n', 1)[1].split('\n\n', 1)[0])
        expected_args = [
            'api', 'repos/fixture/fixture/releases', '--paginate', '--jq',
            r'.[] | select(.draft and (.tag_name | test("^v[0-9]+\\.[0-9]+\\.[0-9]+$"))) | .tag_name',
        ]
        cli = self.workspace / 'gh'
        cli.write_text(
            f'#!{sys.executable}\n'
            'import os, sys\n'
            f'if sys.argv[1:] != {expected_args!r}:\n'
            '    sys.exit("Unexpected GitHub API request: " + repr(sys.argv[1:]))\n'
            'sys.stdout.write(os.environ["PENDING_DRAFT"])\n'
            'sys.exit(int(os.environ["API_EXIT"]))\n'
        )
        cli.chmod(0o755)
        for pending, api_exit, expected in (('', 0, 0), ('v1.3.1', 0, 1), ('', 42, 42)):
            with self.subTest(pending=pending, api_exit=api_exit):
                result = subprocess.run(
                    ['bash', '-e', '-o', 'pipefail', '-c', script], capture_output=True, text=True,
                    env={**os.environ, 'PATH': str(self.workspace) + os.pathsep + os.environ['PATH'],
                         'PENDING_DRAFT': pending, 'API_EXIT': str(api_exit),
                         'GH_REPO': 'fixture/fixture'},
                )
                self.assertEqual(result.returncode, expected, result.stderr)
                if pending:
                    self.assertIn('retry_tag: v1.3.1', result.stdout)

    def workflow_step(self, name):
        workflow = (Path(__file__).resolve().parents[1] /
                    '.github/workflows/release-please.yml').read_text()
        return workflow.split('      - name: ' + name + '\n', 1)[1].split('\n      - ', 1)[0]

    def test_build_does_not_inherit_release_token(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    '.github/workflows/release-please.yml').read_text()
        # Workflow/job env applies to every step; build must not receive secrets.
        for scope in (workflow.split('    steps:', 1)[0],
                      self.workflow_step('Build and validate the release')):
            self.assertNotIn('GH_TOKEN:', scope)
            self.assertNotIn('secrets.', scope)
            self.assertNotIn('github.token', scope)
        for name in ('Require unfinished publication to be resumed first',
                     'Locate the unpublished release commit',
                     'Attach the installable mod and publish'):
            self.assertIn('          GH_TOKEN: ${{ secrets.RELEASE_PLEASE_TOKEN || github.token }}',
                          self.workflow_step(name).split('        run:', 1)[0])

    def test_publication_rechecks_remote_state_before_each_write(self):
        script = textwrap.dedent(self.workflow_step(
            'Attach the installable mod and publish').split('        run: |\n', 1)[1])
        sha = 'a' * 40
        draft = {'isDraft': True, 'tagName': 'v1.3.1', 'targetCommitish': sha}
        dist = self.root / 'build/dist'
        dist.mkdir(parents=True)
        for name in ('Yuoki_1.3.1.zip', 'SHA256SUMS', 'release-notes.md'):
            (dist / name).touch()
        calls = self.workspace / 'calls.json'
        cli = self.workspace / 'gh'
        cli.write_text(f'#!{sys.executable}\n' + textwrap.dedent('''\
            import json, os, pathlib, sys
            log = pathlib.Path(os.environ['CALLS'])
            calls = json.loads(log.read_text())
            args = sys.argv[1:]
            if args == ['api', 'repos/fixture/fixture/git/matching-refs/tags/v1.3.1']:
                state = json.loads(os.environ['TAG_REFS'])[calls.count('refs')]
                if isinstance(state, int):
                    sys.exit(state)
                print(json.dumps(state))
                log.write_text(json.dumps(calls + ['refs']))
                sys.exit(0)
            if args == ['api', 'repos/fixture/fixture/commits/refs/tags/v1.3.1', '--jq', '.sha']:
                state = json.loads(os.environ['TAG_COMMITS'])[calls.count('commit')]
                if isinstance(state, int):
                    sys.exit(state)
                print(state)
                log.write_text(json.dumps(calls + ['commit']))
                sys.exit(0)
            expected = {
                'view': ['release', 'view', 'v1.3.1', '--json', 'isDraft,targetCommitish,tagName'],
                'upload': ['release', 'upload', 'v1.3.1', 'build/dist/Yuoki_1.3.1.zip',
                           'build/dist/SHA256SUMS', '--clobber'],
                'edit': ['release', 'edit', 'v1.3.1', '--notes-file',
                         'build/dist/release-notes.md', '--draft=false'],
            }
            if len(args) < 2 or args != expected.get(args[1]):
                sys.exit('Unexpected gh request: ' + repr(args))
            if args[1] == 'view':
                state = json.loads(os.environ['STATES'])[calls.count('view')]
                if isinstance(state, int):
                    sys.exit(state)
                print(json.dumps(state))
            calls.append(args[1])
            log.write_text(json.dumps(calls))
            '''))
        cli.chmod(0o755)
        cases = [([draft, draft], ['view', 'refs', 'upload', 'view', 'refs', 'edit'], 0)]
        for changed in ({**draft, 'isDraft': False}, {**draft, 'targetCommitish': 'b' * 40},
                        {**draft, 'tagName': 'v1.3.2'}, 42):
            cases.append(([changed], [] if changed == 42 else ['view'], 42 if changed == 42 else 1))
            cases.append(([draft, changed], ['view', 'refs', 'upload'] + ([] if changed == 42 else ['view']),
                          42 if changed == 42 else 1))
        # A missing tag is normal for drafts. Prefix matches must not count.
        prefix = [{'ref': 'refs/tags/v1.3.10'}]
        matching = [{'ref': 'refs/tags/v1.3.1', 'object': {'type': 'commit', 'sha': sha}}]
        annotated = [{'ref': 'refs/tags/v1.3.1', 'object': {'type': 'tag', 'sha': 'c' * 40}}]
        tag_cases = [([prefix, prefix], [], ['view', 'refs', 'upload', 'view', 'refs', 'edit'], 0)]
        for refs in (matching, annotated):
            tag_cases.extend([
                ([refs, refs], [sha, sha], ['view', 'refs', 'commit', 'upload', 'view', 'refs', 'commit', 'edit'], 0),
                ([refs], ['b' * 40], ['view', 'refs', 'commit'], 1),
                ([[], refs], ['b' * 40], ['view', 'refs', 'upload', 'view', 'refs', 'commit'], 1),
                ([refs], [42], ['view', 'refs'], 42),
            ])
        tag_cases.extend([([42], [], ['view'], 42), ([[], 42], [], ['view', 'refs', 'upload', 'view'], 42)])
        all_cases = [(states, [[], []], [], calls, code) for states, calls, code in cases]
        all_cases += [([draft, draft], refs, commits, calls, code)
                      for refs, commits, calls, code in tag_cases]
        for states, refs, commits, expected_calls, expected_exit in all_cases:
            with self.subTest(states=states, refs=refs, commits=commits):
                calls.write_text('[]')
                result = subprocess.run(
                    ['bash', '-e', '-o', 'pipefail', '-c', script], cwd=self.root,
                    capture_output=True, text=True,
                    env={**os.environ, 'PATH': str(self.workspace) + os.pathsep + os.environ['PATH'],
                         'TAG': 'v1.3.1', 'RELEASE_SHA': sha, 'RUNNER_TEMP': str(self.workspace),
                         'CALLS': str(calls), 'STATES': json.dumps(states), 'GH_REPO': 'fixture/fixture',
                         'TAG_REFS': json.dumps(refs), 'TAG_COMMITS': json.dumps(commits)},
                )
                self.assertEqual(result.returncode, expected_exit, result.stderr)
                self.assertEqual(json.loads(calls.read_text()), expected_calls)


if __name__ == '__main__':
    unittest.main(defaultTest='ReleaseTests')
