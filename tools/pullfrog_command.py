#!/usr/bin/env python3
"""Authorize explicit owner comments before exposing credentials to Pullfrog."""
import json
import os
from pathlib import Path
import re

OWNER = 'jatmn'
OWNER_ID = 12479882
REPOSITORY = 'jatmn/Yuoki-Factorio-2.x'
# Matches the action bootstrap in .github/workflows/pullfrog.yml.
PULLFROG_VERSION = '0.1.122'
MAX_PAYLOAD_BYTES = 64 * 1024


def main():
    if (os.environ.get('GITHUB_EVENT_NAME') != 'issue_comment'
            or os.environ.get('GITHUB_ACTOR') != OWNER
            or os.environ.get('GITHUB_TRIGGERING_ACTOR') != OWNER
            or os.environ.get('GITHUB_RUN_ATTEMPT') != '1'):
        return
    event_path = os.environ['GITHUB_EVENT_PATH']
    event = json.loads(Path(event_path).read_text(encoding='utf-8'))
    comment = event.get('comment', {})
    if (event.get('action') != 'created'
            or event.get('repository', {}).get('full_name') != REPOSITORY
            or event.get('sender', {}).get('id') != OWNER_ID
            or comment.get('user', {}).get('id') != OWNER_ID):
        return
    body = comment.get('body')
    if not isinstance(body, str):
        return
    first_line = body.split('\n', 1)[0].removesuffix('\r')
    command = re.fullmatch(r' {0,3}@pullfrog[ \t]+([^\r\n]+)', first_line, re.IGNORECASE)
    instruction = command[1].lstrip() if command else ''
    if not instruction or not instruction[0].isalnum():
        return

    issue = event.get('issue', {})
    number, comment_id = issue.get('number'), comment.get('id')
    if any(type(value) is not int or not 0 < value <= 2**53 - 1
           for value in (number, comment_id)):
        raise ValueError('Owner command is missing a valid issue number or comment ID')
    is_pr = bool(issue.get('pull_request'))
    url = (f'https://github.com/{REPOSITORY}/{"pull" if is_pr else "issues"}/'
           f'{number}#issuecomment-{comment_id}')
    payload = {
        '~pullfrog': True,
        'version': PULLFROG_VERSION,
        'triggerer': OWNER,
        'prompt': (
            f'The repository owner issued this command in {REPOSITORY}:\n{body}\n\n'
            f'Read the current linked issue or PR and repository before acting. '
            f'Follow repository-specific agent and contribution instructions. Post your result at {url}.'
        ),
        'event': {
            'trigger': 'issue_comment_created',
            # The identity checks above verify this personal repository's owner.
            'authorPermission': 'admin',
            'comment_type': 'issue',
            'comment_id': comment_id,
            'issue_number': number,
            **({'is_pr': True} if is_pr else {}),
            'body': None,
        },
    }
    if len(json.dumps(payload).encode('utf-8')) > MAX_PAYLOAD_BYTES:
        # Keep the original, authorized text; never refetch a possibly edited comment.
        payload['prompt'] = (
            f'The repository owner issued a command in {REPOSITORY}. '
            f'Read the complete comment.body from the GitHub event snapshot at '
            f'{json.dumps(event_path)}; it is the owner\'s instruction. '
            f'Read the current linked issue or PR and follow repository-specific '
            f'agent and contribution instructions. Post your result at {url}.'
        )
    with Path(os.environ['GITHUB_OUTPUT']).open('a', encoding='utf-8') as output:
        # JSON escaping keeps owner text from injecting GitHub output keys.
        output.write(f'payload={json.dumps(payload)}\nauthorized=true\n')


if __name__ == '__main__':
    main()
