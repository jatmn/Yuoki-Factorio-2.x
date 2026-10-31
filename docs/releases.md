# Releasing Yuoki

The **Release Please** workflow maintains a **draft release PR** on `main`.
Continue merging normal changes and adding player-facing entries to
`changelog.txt` while that PR is open. No release is published until you mark
the release PR ready and merge it. Merging the workflow setup PR only enables
this process; it does not publish 1.3.1.

## First release: 1.3.1

The empty manifest means Release Please has not published this repository yet.
`initial-version: 1.3.1` fixes the first proposed version even if more features
arrive before release. The bootstrap boundary is
`50ea38b9703a13e8644c3bcfe6e400b3bf2b4a5c`, the completed 1.3.0 merge,
immediately before the graphics fixes in #21. Earlier history is excluded.
After the first release, Release Please uses its published release and manifest
to calculate subsequent versions from Conventional Commits. There is no
permanent `release-as` override to remove.

Release Please updates `info.json`, `.github/version.txt` and
`.github/.release-please-manifest.json` in its PR. It does **not** rewrite
`changelog.txt` or create a second generated changelog. Its PR body summarizes
Conventional Commits; published release notes use only the matching newest
author-written section of `changelog.txt`.

## Maintainer sequence

1. Merge normal PRs using Conventional Commit titles (`fix:`, `feat:`, etc.).
   Authors add entries to the current unreleased section of `changelog.txt`.
2. Inspect the draft release PR, including the proposed version. For subsequent
   releases, create/update the newest changelog section to match that version
   and keep the release date current. The historic `info.json.date` field is
   descriptive metadata; Factorio does not require it for loading.
3. Mark the release PR ready, review checks and merge when ready to publish.
   Keep Release Please's branch, title/body structure and autorelease labels.
4. The workflow creates an unpublished GitHub draft, checks out the exact
   release merge commit, requires tag/manifest/metadata/changelog agreement,
   builds and validates the ZIP, uploads it with `SHA256SUMS`, and publishes.
   Older changelog sections remain inside the mod but are absent from that
   GitHub release's notes.

Download the release asset **`Yuoki_1.3.1.zip`** (or the corresponding later
version) and copy it unchanged into Factorio's mods directory. GitHub's automatic
**Source code** archives are not the installable asset. The mod currently requires
Factorio **2.1.20 or later in the 2.1 series**, as declared in `info.json`.
Existing incompatible mods listed there still cannot be enabled alongside Yuoki.

## Permissions and failures

The workflow uses `GITHUB_TOKEN` by default and requests contents, issues and
pull-request write permissions. Repository **Settings → Actions → General →
Allow GitHub Actions to create and approve pull requests** must be enabled.
It is already enabled at setup time.

GitHub suppresses normal PR-triggered CI for PRs created/updated by
`GITHUB_TOKEN`. To have CI automatically run on each release PR update, supply
the optional Actions secret **`RELEASE_PLEASE_TOKEN`**, using a fine-grained PAT
with this repository's Contents, Issues and Pull requests read/write access.
Without it, a maintainer can close/reopen the release PR to trigger PR checks;
the publication workflow always validates the package regardless.

Build/upload failures leave the release unpublished. Fix transient problems,
then run **Release Please** manually on **main**, with `retry_tag` set to the
existing draft tag (for example `v1.3.1`). This rebuilds its recorded commit,
replaces incomplete assets and publishes only after validation. An already
published release is rejected. Normal runs pause while a versioned release
draft remains unpublished, so they cannot propose another release using that
unfinished release's history. A source defect in the recorded release commit
must be corrected through a new reviewed release; retrying does not silently
substitute newer main-branch code. A blank manual input resumes normal Release
Please operation.

Local release preparation, on a release PR checkout where the manifest already
contains the proposed version:

```sh
python3 tools/test_prepare_release.py
python3 tools/prepare_release.py --tag v1.3.1
```

The existing `tools/package.py` / `tools/validate_package.py` commands still
build development ZIPs without requiring a merged release manifest.

## Verified requirements and sources

- [Factorio 2.1.24 mod structure](https://lua-api.factorio.com/2.1.24/auxiliary/mod-structure.html):
  ZIP filename `{name}_{version}.zip`, one enclosing mod folder with
  `info.json`, matching name/version, mandatory name/version/title/author,
  version components in 0–65535 and explicit `factorio_version: "2.1"`.
  The enclosing folder's name is unrestricted by Factorio; our builder uses
  `Yuoki_<version>/` consistently. Dependencies in `info.json` also apply.
- [Factorio changelog format](https://lua-api.factorio.com/2.1.24/auxiliary/changelog-format.html):
  the in-game history uses 99-dash separators, version lines, two-space
  categories and four-space bullet entries. Existing historical text is
  preserved. Release preparation checks the current section/version; it does
  not claim to lint every historical entry.
- [Release Please bootstrap and manifest configuration](https://github.com/googleapis/release-please/blob/main/docs/manifest-releaser.md)
  and [configuration schema](https://github.com/googleapis/release-please/blob/main/schemas/config.json):
  initial version, bootstrap boundary, draft PR/release settings and JSON updates.
- [Release Please Action permissions and token behavior](https://github.com/googleapis/release-please-action#other-actions-on-release-please-prs).

ZIP validation checks tracked membership, exact source bytes, required notices,
CRC and checksum. It does not replace Factorio engine, save or graphics testing
for gameplay changes. This workflow publishes GitHub assets, not Mod Portal uploads.
