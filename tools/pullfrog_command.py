#!/usr/bin/env python3
"""Authorize owner comments and automatic PR review before running Pullfrog."""
from http.client import IncompleteRead
import json
import os
from pathlib import Path
import re
import sys
from time import sleep
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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


def is_authorized_review(payload, api_url, repository, token):
    """Verify the author from GitHub, independent of the actor who pushed."""
    if not isinstance(payload, dict) or payload.get('~pullfrog') is not True:
        return False
    event = payload.get('event')
    if not isinstance(event, dict) or event.get('is_pr') is not True:
        return False
    if event.get('trigger') not in (
        'pull_request_opened', 'pull_request_ready_for_review', 'pull_request_synchronize',
    ):
        return False
    number = event.get('issue_number')
    if type(number) is not int or not 0 < number <= 2**53 - 1:
        return False

    request = Request(f'{api_url}/repos/{repository}/pulls/{number}', headers={
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json',
    })
    last_error = None
    for delay in (0, 0.25, 0.75):
        if delay:
            sleep(delay)
        try:
            with urlopen(request, timeout=10) as response:
                pr = json.load(response)
            author = pr.get('user') if isinstance(pr, dict) else None
            return (isinstance(author, dict)
                    and author.get('id') == OWNER_ID and author.get('login') == OWNER)
        except HTTPError as error:
            last_error = RuntimeError(f'GitHub HTTP {error.code}')
            retry = (error.code == 408 or error.code >= 500) and not error.headers.get('Retry-After')
            error.close()
            if not retry:
                break
        except (URLError, TimeoutError, ConnectionError, IncompleteRead) as error:
            last_error = error
    raise RuntimeError(f'Could not verify PR #{number} author.') from last_error


def review_main():
    authorized = is_authorized_review(
        json.loads(os.environ['PULLFROG_PROMPT']),
        os.environ['GITHUB_API_URL'],
        os.environ['GITHUB_REPOSITORY'],
        os.environ['GH_TOKEN'],
    )
    if authorized:
        with Path(os.environ['GITHUB_OUTPUT']).open('a', encoding='utf-8') as output:
            output.write('authorized=true\n')
    else:
        print('Skipping automatic review. The dispatch must target an owner-authored PR.')


if __name__ == '__main__':
    if sys.argv[1:] == ['--review']:
        review_main()
    else:
        main()
