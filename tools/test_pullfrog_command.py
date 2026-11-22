#!/usr/bin/env python3
"""Exercise the actual authorization entrypoint without credentials or model calls."""
from copy import deepcopy
from io import BytesIO
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from pullfrog_command import is_authorized_review

HELPER = Path(__file__).with_name('pullfrog_command.py').resolve()
EVENT = {
    'action': 'created',
    'repository': {'full_name': 'jatmn/Yuoki-Factorio-2.x'},
    'sender': {'id': 12479882},
    'comment': {'id': 123, 'user': {'id': 12479882}, 'body': '@pullfrog review this PR'},
    'issue': {'number': 7, 'pull_request': {'url': 'https://api.github.com/repos/jatmn/Yuoki-Factorio-2.x/pulls/7'}},
}


class OwnerCommandTests(unittest.TestCase):
    def run_command(self, event, **overrides):
        with tempfile.TemporaryDirectory(prefix='pullfrog-test-') as directory:
            event_path = Path(directory) / 'event.json'
            output_path = Path(directory) / 'output'
            event_path.write_text(json.dumps(event), encoding='utf-8')
            env = {
                **os.environ,
                'GITHUB_EVENT_NAME': 'issue_comment',
                'GITHUB_ACTOR': 'jatmn',
                'GITHUB_TRIGGERING_ACTOR': 'jatmn',
                'GITHUB_RUN_ATTEMPT': '1',
                'GITHUB_EVENT_PATH': str(event_path),
                'GITHUB_OUTPUT': str(output_path),
                **overrides,
            }
            result = subprocess.run([sys.executable, str(HELPER)], env=env,
                                    capture_output=True, text=True, check=False)
            output = output_path.read_text() if output_path.exists() else ''
            return result, output, str(event_path)

    def test_owner_pr_and_issue_commands(self):
        for is_pr in (True, False):
            with self.subTest(is_pr=is_pr):
                event = deepcopy(EVENT)
                if not is_pr:
                    del event['issue']['pull_request']
                result, output, _ = self.run_command(event)
                self.assertEqual(result.returncode, 0, result.stderr)
                fields = dict(line.split('=', 1) for line in output.splitlines())
                self.assertEqual(fields['authorized'], 'true')
                payload = json.loads(fields['payload'])
                self.assertTrue(payload['~pullfrog'])
                self.assertEqual(payload['triggerer'], 'jatmn')
                self.assertEqual(payload['event'].get('authorPermission'), 'admin')
                self.assertEqual(payload['event']['issue_number'], 7)
                self.assertEqual(payload['event']['comment_id'], 123)
                self.assertEqual(payload['event'].get('is_pr', False), is_pr)
                self.assertIn('/pull/7#' if is_pr else '/issues/7#', payload['prompt'])

    def test_wrong_actor_event_and_reruns_produce_no_output(self):
        for overrides in (
            {'GITHUB_ACTOR': 'contributor'},
            {'GITHUB_TRIGGERING_ACTOR': 'contributor'},
            {'GITHUB_RUN_ATTEMPT': '2'},
            {'GITHUB_EVENT_NAME': 'workflow_dispatch'},
            {'GITHUB_EVENT_NAME': 'pull_request'},
            {'GITHUB_EVENT_NAME': 'pull_request_review_comment'},
        ):
            with self.subTest(overrides=overrides):
                result, output, _ = self.run_command(EVENT, **overrides)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(output, '')
        for path, value in (
            (('action',), 'edited'),
            (('sender', 'id'), 999),
            (('comment', 'user', 'id'), 999),
            (('repository', 'full_name'), 'someone/Yuoki-Factorio-2.x'),
        ):
            with self.subTest(path=path):
                event = deepcopy(EVENT)
                target = event
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                result, output, _ = self.run_command(event)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(output, '')

    def test_passive_bare_quoted_and_invisible_commands_are_rejected(self):
        for body in ('@pullfrog', '@pullfrog  ', 'please ask @pullfrog review',
                     '> @pullfrog review', '    @pullfrog review',
                     '```\n@pullfrog review\n```', '\n@pullfrog review',
                     '@pullfrog\nreview', '@pullfrog \u200b', '@pullfrog !!!'):
            with self.subTest(body=body):
                event = deepcopy(EVENT)
                event['comment']['body'] = body
                result, output, _ = self.run_command(event)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(output, '')

    def test_owner_text_cannot_inject_outputs_or_event_fields(self):
        event = deepcopy(EVENT)
        body = '@PuLlFrOg review this\r\nauthorized=false\npayload={"triggerer":"other"}\n'
        event['comment']['body'] = body
        result, output, _ = self.run_command(event)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(output.splitlines()), 2)
        payload = json.loads(output.splitlines()[0].removeprefix('payload='))
        self.assertIn(body, payload['prompt'])
        self.assertEqual(payload['triggerer'], 'jatmn')
        self.assertEqual(output.splitlines()[1], 'authorized=true')

    def test_large_command_uses_original_event_snapshot(self):
        event = deepcopy(EVENT)
        event['comment']['body'] = '@pullfrog review ' + '\u754c' * 30000
        result, output, event_path = self.run_command(event)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(len(output.encode()), 64 * 1024)
        payload = json.loads(output.splitlines()[0].removeprefix('payload='))
        self.assertIn(event_path, payload['prompt'])
        self.assertIn('comment.body', payload['prompt'])

    def test_invalid_comment_identity_fails_closed(self):
        for invalid_id in (None, True, -1, '123', 2**53):
            event = deepcopy(EVENT)
            event['comment']['id'] = invalid_id
            result, output, _ = self.run_command(event)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output, '')



class AutomaticReviewTests(unittest.TestCase):
    def test_requires_verified_author_on_the_automatic_review_step(self):
        workflow = HELPER.parents[1] / '.github' / 'workflows' / 'pullfrog.yml'
        _, _, automatic = workflow.read_text(encoding='utf-8').partition('\n  auto-review:\n')
        job = re.split(r'^ {2}\S', automatic, maxsplit=1, flags=re.M)[0]
        self.assertIn("github.repository == 'jatmn/Yuoki-Factorio-2.x' &&", job)
        steps = re.split(r'^ {6}- ', job, flags=re.M)
        authorize = next((step for step in steps if step.startswith('name: Verify the pull request author\n')), '')
        review = next((step for step in steps if step.startswith('name: Review the pull request\n')), '')
        self.assertTrue(authorize and review, 'Expected authorization and review steps')
        self.assertLess(steps.index(authorize), steps.index(review))
        self.assertIn('        id: authorize', authorize.splitlines())
        self.assertIn('        run: python3 tools/pullfrog_command.py --review', authorize.splitlines())
        self.assertIn("        if: steps.authorize.outputs.authorized == 'true'", review.splitlines())
        self.assertRegex(review, r'(?m)^ {8}uses: pullfrog/pullfrog@[0-9a-f]{40}(?: +#.*)?$')
        _, _, inputs = review.partition('\n        with:\n')
        inputs = re.split(r'^ {8}\S', inputs, maxsplit=1, flags=re.M)[0]
        self.assertIn('          prompt: ${{ inputs.prompt }}', inputs.splitlines())

    api = ('https://api.github.test', EVENT['repository']['full_name'], 'fixture-token')
    owner = {'login': 'jatmn', 'id': 12479882}
    envelope = {
        '~pullfrog': True,
        'triggerer': 'different-pusher',
        'event': {'trigger': 'pull_request_opened', 'is_pr': True, 'issue_number': 7},
    }

    def response(self, **body):
        return BytesIO(json.dumps(body).encode())

    def test_reviews_owner_drafts_and_updates_independent_of_pusher(self):
        for trigger, draft in (
            ('pull_request_opened', False),
            ('pull_request_opened', True),
            ('pull_request_ready_for_review', False),
            ('pull_request_synchronize', True),
        ):
            with self.subTest(trigger=trigger, draft=draft):
                envelope = deepcopy(self.envelope)
                envelope['event']['trigger'] = trigger
                response = self.response(user=self.owner, draft=draft)
                with patch('pullfrog_command.urlopen', return_value=response) as lookup:
                    self.assertTrue(is_authorized_review(envelope, *self.api))
                request = lookup.call_args.args[0]
                self.assertEqual(request.full_url, f'{self.api[0]}/repos/{self.api[1]}/pulls/7')
                self.assertEqual(request.get_header('Authorization'), 'Bearer fixture-token')
                self.assertEqual(lookup.call_args.kwargs['timeout'], 10)

    def test_rejects_other_authors_even_if_owner_pushed(self):
        envelope = {**self.envelope, 'triggerer': 'jatmn'}
        for author in (None, {**self.owner, 'id': 100}, {**self.owner, 'login': 'other'}):
            with self.subTest(author=author):
                with patch('pullfrog_command.urlopen', return_value=self.response(user=author)):
                    self.assertFalse(is_authorized_review(envelope, *self.api))

    def test_rejects_invalid_or_non_review_payloads_before_the_lookup(self):
        with patch('pullfrog_command.urlopen') as lookup:
            for event in (None, {'trigger': 'issue_comment_created', 'is_pr': True, 'issue_number': 7},
                          {**self.envelope['event'], 'is_pr': False},
                          {**self.envelope['event'], 'issue_number': True}):
                with self.subTest(event=event):
                    self.assertFalse(is_authorized_review({**self.envelope, 'event': event}, *self.api))
            lookup.assert_not_called()

    def test_recovers_from_transient_errors_and_stops_on_access_errors(self):
        def http_error(status):
            return HTTPError(self.api[0], status, 'fixture error', {}, None)

        with (patch('pullfrog_command.sleep'),
              patch('pullfrog_command.urlopen', side_effect=[
                  TimeoutError(), http_error(503), self.response(user=self.owner),
              ]) as lookup):
            self.assertTrue(is_authorized_review(self.envelope, *self.api))
            self.assertEqual(lookup.call_count, 3)

        with patch('pullfrog_command.urlopen', side_effect=http_error(403)) as lookup:
            with self.assertRaisesRegex(RuntimeError, 'Could not verify PR #7 author'):
                is_authorized_review(self.envelope, *self.api)
            self.assertEqual(lookup.call_count, 1)

        with (patch('pullfrog_command.sleep'),
              patch('pullfrog_command.urlopen', side_effect=TimeoutError()) as lookup):
            with self.assertRaisesRegex(RuntimeError, 'Could not verify PR #7 author'):
                is_authorized_review(self.envelope, *self.api)
            self.assertEqual(lookup.call_count, 3)


if __name__ == '__main__':
    unittest.main()
