#!/usr/bin/env python3
"""Regressions for CI routing and Lua selection; no game or dependency mods are loaded."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

from ci_changes import classify

ROUTER = Path(__file__).with_name('ci_changes.py').resolve()


def workflow_block(workflow, name):
    text = (ROUTER.parents[1] / '.github/workflows' / workflow).read_text()
    step = text.split(f'      - name: {name}\n', 1)[1].split('      - name:', 1)[0]
    lines = []
    for line in step.split('        run: |\n', 1)[1].splitlines():
        if line.strip() and not line.startswith('          '):
            break
        lines.append(line)
    return textwrap.dedent('\n'.join(lines))


class RoutingTests(unittest.TestCase):
    def test_dispatcher_does_not_execute_changed_router(self):
        command = workflow_block('ci.yml', 'Route the complete Git diff')
        for has_base_router in (True, False):
            with self.subTest(has_base_router=has_base_router), \
                    tempfile.TemporaryDirectory(prefix='yuoki-dispatch-') as directory:
                root = Path(directory)

                def git(*args):
                    return subprocess.check_output([
                        'git', '-c', 'user.name=CI test', '-c', 'user.email=ci@example.invalid', *args
                    ], cwd=root, text=True).strip()

                git('init', '-q')
                (root / 'tools').mkdir()
                router = root / 'tools/ci_changes.py'
                if has_base_router:
                    shutil.copy(ROUTER, router)
                git('add', '.'); git('commit', '--allow-empty', '-qm', 'base')
                base = git('rev-parse', 'HEAD')
                router.write_text('print("lua=false\\npython=false\\npackage=false\\nworkflows=false")\n')
                (root / 'control.lua').write_text('return (\n')
                git('add', '.'); git('commit', '-qm', 'broken Lua with disabled router')
                output = root / 'outputs'
                scratch = root / 'scratch'
                scratch.mkdir()
                subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', command], cwd=root, check=True,
                               env={**os.environ, 'BASE': base, 'GITHUB_OUTPUT': str(output),
                                    'RUNNER_TEMP': str(scratch)})
                self.assertEqual(set(output.read_text().splitlines()), {
                    'lua=true', 'python=true', 'package=true', 'workflows=true'
                })

    @unittest.skipUnless(shutil.which('luac5.2'), 'Lua workflow installs the required Lua 5.2 compiler')
    def test_lua_workflow_checks_option_like_names(self):
        with tempfile.TemporaryDirectory(prefix='yuoki-lua-option-') as directory:
            root = Path(directory)

            def git(*args):
                return subprocess.check_output([
                    'git', '-c', 'user.name=CI test', '-c', 'user.email=ci@example.invalid', *args
                ], cwd=root, text=True).strip()

            git('init', '-q')
            shutil.copy(ROUTER.parents[1] / '.luacheckrc', root / '.luacheckrc')
            git('add', '.'); git('commit', '-qm', 'base')
            base = git('rev-parse', 'HEAD')
            (root / '-generated.lua').write_text('return true\n')
            git('add', '.'); git('commit', '-qm', 'option-like Lua name')
            for name in ('Select Lua files for this event', 'Check Lua syntax'):
                subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', workflow_block('lua.yml', name)],
                               cwd=root, env={**os.environ, 'BASE': base, 'EVENT_NAME': 'pull_request'}, check=True)

    def test_lua_workflow_selects_type_changes(self):
        workflow = ROUTER.parents[1] / '.github/workflows/lua.yml'
        step = workflow.read_text().split('      - name: Select Lua files for this event\n', 1)[1]
        selection = textwrap.dedent(step.split('        run: |\n', 1)[1].split('      - name:', 1)[0])
        for starts_as_symlink in (False, True):
            with self.subTest(starts_as_symlink=starts_as_symlink), \
                    tempfile.TemporaryDirectory(prefix='yuoki-ci-type-') as directory:
                root = Path(directory)

                def git(*args):
                    return subprocess.check_output([
                        'git', '-c', 'user.name=CI test', '-c', 'user.email=ci@example.invalid', *args
                    ], cwd=root, text=True).strip()

                git('init', '-q')
                (root / 'docs').mkdir()
                (root / 'docs/source').write_text('return true\n')
                (root / 'untouched.lua').write_text('return true\n')
                lua = root / 'control.lua'
                if starts_as_symlink:
                    lua.symlink_to('docs/source')
                else:
                    lua.write_text('return true\n')
                git('add', '.'); git('commit', '-qm', 'base')
                base = git('rev-parse', 'HEAD')
                lua.unlink()
                if starts_as_symlink:
                    lua.write_text('invalid Lua source\n')
                else:
                    lua.symlink_to('docs/source')
                    (root / 'docs/source').write_text('invalid Lua source\n')
                git('add', '.'); git('commit', '-qm', 'change Lua file type')
                self.assertIn('T\tcontrol.lua', git('diff', '--name-status', base, 'HEAD').splitlines())
                routed = subprocess.check_output(
                    [sys.executable, str(ROUTER), '--base', base], cwd=root, text=True
                ).splitlines()
                self.assertIn('lua=true', routed)
                for event in ('pull_request', 'push'):
                    subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', selection], cwd=root,
                                   env={**os.environ, 'BASE': base, 'EVENT_NAME': event}, check=True)
                    self.assertEqual((root / '.cache/ci-lua-files').read_bytes(),
                                     b'control.lua\0' if event == 'pull_request'
                                     else b'control.lua\0untouched.lua\0')

    def test_lua_workflow_pr_and_push_manifests(self):
        selection = workflow_block('lua.yml', 'Select Lua files for this event')
        with tempfile.TemporaryDirectory(prefix='yuoki-lua-manifest-') as directory:
            root = Path(directory)

            def git(*args):
                return subprocess.check_output([
                    'git', '-c', 'user.name=CI test', '-c', 'user.email=ci@example.invalid', *args
                ], cwd=root, text=True).strip()

            def select(base, event):
                subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', selection], cwd=root,
                               env={**os.environ, 'BASE': base, 'EVENT_NAME': event}, check=True)
                return set(filter(None, (root / '.cache/ci-lua-files').read_bytes().split(b'\0')))

            git('init', '-q')
            for name in ('untouched.lua', 'deleted.lua', 'old.lua'):
                (root / name).write_text('return true\n')
            git('add', '.'); git('commit', '-qm', 'base')
            # Lint/formatter/toolchain changes must check the full baseline on both events.
            for config in ('.luacheckrc', '.stylua.toml', '.github/workflows/lua.yml'):
                base = git('rev-parse', 'HEAD')
                (root / config).parent.mkdir(parents=True, exist_ok=True)
                (root / config).write_text('# manifest fixture\n')
                git('add', '.'); git('commit', '-qm', 'configuration')
                for event in ('pull_request', 'push'):
                    self.assertEqual(select(base, event),
                                     {b'untouched.lua', b'deleted.lua', b'old.lua'})
            base = git('rev-parse', 'HEAD')
            unusual = 'new file\nwith $shell; characters.lua'
            git('mv', 'old.lua', unusual)
            git('rm', 'deleted.lua')
            (root / '-added.lua').write_text('return false\n')
            (root / 'untracked.lua').write_text('return true\n')
            git('add', '--', '-added.lua'); git('commit', '-qm', 'rename, delete and add')
            self.assertEqual(select(base, 'pull_request'), {os.fsencode(unusual), b'-added.lua'})
            self.assertEqual(select(base, 'push'),
                             {os.fsencode(unusual), b'-added.lua', b'untouched.lua'})
            for event in ('pull_request', 'push'):
                failed = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', selection],
                                        cwd=root, capture_output=True,
                                        env={**os.environ, 'BASE': 'missing-revision', 'EVENT_NAME': event})
                self.assertNotEqual(failed.returncode, 0)

    def test_surface_selection(self):
        cases = [
            (['control.lua'], {'lua', 'package'}),
            (['prototypes/new/module.lua'], {'lua', 'package'}),
            (['tests/runtime.lua'], {'lua'}),
            (['tests/prototypes.py', 'tools/test.py'], {'python'}),
            (['tools/pullfrog_command.py'], {'python', 'workflows'}),
            (['tools/test_pullfrog_command.py'], {'python', 'workflows'}),
            (['.ruff.toml'], {'python'}),
            (['.github/release-please-config.json'], {'python'}),
            (['.github/.release-please-manifest.json'], {'python'}),
            (['.github/version.txt'], {'python'}),
            (['tools/package.py', 'tools/validate_package.py'], {'python', 'package'}),
            (['info.json', 'locale/en/yuoki.cfg', 'graphics/new.png'], {'package'}),
            (['README.md', 'NOTICE', 'graphics/README.md'], {'package'}),
            (['docs/development.md', 'AGENTS.md', 'CONTRIBUTING.md'], set()),
            (['.gitignore', '.github/CODEOWNERS', 'build/generated.txt'], set()),
            (['.luacheckrc', '.stylua.toml'], {'lua'}),
            (['.github/workflows/lua.yml'], {'lua', 'python', 'workflows'}),
            (['.github/workflows/python.yml'], {'python', 'workflows'}),
            (['.github/workflows/package.yml'], {'python', 'package', 'workflows'}),
            (['.github/workflows/workflows.yml'], {'python', 'workflows'}),
            (['.github/workflows/pullfrog.yml'], {'python', 'workflows'}),
            (['.github/workflows/pullfrog-checks.yml'], {'python', 'workflows'}),
            (['.github/workflows/ci.yml'], {'lua', 'python', 'package', 'workflows'}),
            (['tools/ci_changes.py'], {'lua', 'python', 'package', 'workflows'}),
            (['control.lua', 'tools/test.py'], {'lua', 'python', 'package'}),
            ([], set()),
        ]
        for paths, expected in cases:
            with self.subTest(paths=paths):
                self.assertEqual({name for name, enabled in classify(paths).items() if enabled}, expected)

    def test_complete_git_diff_and_path_changes(self):
        with tempfile.TemporaryDirectory(prefix='yuoki-ci-') as directory:
            root = Path(directory)

            def git(*args):
                return subprocess.check_output([
                    'git', '-c', 'user.name=CI test', '-c', 'user.email=ci@example.invalid', *args
                ], cwd=root, text=True).strip()

            def route(base):
                result = subprocess.check_output(
                    [sys.executable, str(ROUTER), '--base', base], cwd=root, text=True
                )
                return {line.split('=')[0] for line in result.splitlines() if line.endswith('=true')}

            git('init', '-q')
            git('commit', '--allow-empty', '-qm', 'base')
            base = git('rev-parse', 'HEAD')
            (root / 'docs').mkdir()
            for index in range(3500):
                (root / 'docs' / f'{index:04}.md').write_text('documentation\n')
            git('add', '.'); git('commit', '-qm', 'large docs-only change')
            self.assertEqual(route(base), set())
            (root / 'tests').mkdir()
            lua = root / 'tests/late file\nwith whitespace.lua'
            lua.write_text('return true\n')
            git('add', '.'); git('commit', '-qm', 'Lua beyond the filtered file-list cap')
            self.assertEqual(route(base), {'lua'})
            previous = git('rev-parse', 'HEAD')
            git('mv', str(lua.relative_to(root)), 'tools-renamed.py')
            git('commit', '-qm', 'cross-surface rename')
            self.assertEqual(route(previous), {'lua', 'python', 'package'})
            previous = git('rev-parse', 'HEAD')
            git('rm', 'tools-renamed.py'); git('commit', '-qm', 'delete')
            self.assertEqual(route(previous), {'python', 'package'})
            failed = subprocess.run([sys.executable, str(ROUTER), '--base', 'missing-revision'],
                                    cwd=root, capture_output=True, text=True)
            self.assertNotEqual(failed.returncode, 0)
            self.assertEqual(failed.stdout, '')


if __name__ == '__main__':
    unittest.main()
