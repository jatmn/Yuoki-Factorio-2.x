# Contributing

Search existing issues and pull requests for overlapping work, then use a topic
branch and a focused PR against the intended maintenance branch. Preserve
upstream attribution and [Licence.txt](Licence.txt). Do not bump `info.json`,
publish a release, or change gameplay as part of unrelated tooling work.

## Validation before commits and PR updates

Review every changed hunk and run `git diff --check` for every change. Run the
applicable checks below from the repository root before committing or pushing
a PR update; rerun affected checks after repairs. See
[development](docs/development.md) for the CI routing and tool versions.

- Lua: format each added or modified file with **StyLua 2.5.2** and the root
  `.stylua.toml`, then check it with `luac5.2 -p`, **Luacheck 1.2.0** and
  `stylua --check --config-path .stylua.toml`. Also syntax-check `.luacheckrc`.
  Resolve warnings in touched files without blanket suppressions. The Lua
  baseline is established; preserve it without reformatting unrelated files.
- Python/tools: parse tracked Python files without importing or executing game
  code, lint every tracked Python file with **Ruff 0.17.3**
  (`git ls-files -z -- '*.py' | xargs -0 -r ruff check --config .ruff.toml --`)
  and run `python3 tools/test_ci_changes.py` plus
  `python3 tools/test_pullfrog_command.py` and `python3 tools/test_package.py`.
  Release tooling also requires `python3 tools/test_prepare_release.py`.
- Workflows: run **actionlint 1.7.12**. Changes to the CI dispatcher or router
  require all lightweight checks, including the Lua configuration probes.
- Shipped sources, metadata, locale, graphics, license notices or packaging
  tools: run `python3 tools/package.py` and
  `python3 tools/validate_package.py`. Inspect the intended ZIP contents.
- Documentation: verify links, commands and the resulting diff.

Lua CI checks changed files on PRs and all tracked Lua files on relevant pushes
to `main` and `release/1.3.0`, and on PRs that change the Luacheck/StyLua
configuration or the Lua workflow.
Formatting a touched file can create a mechanical diff within that file; keep
it separate from behavioral edits where practical. Do not reformat the whole
repository during ordinary contribution work.

Lightweight CI does not load Factorio. For gameplay and compatibility changes,
also validate with the supported Factorio version, relevant optional mods and
existing saves where affected. Report the exact versions, commands, results
and any untested engine or graphical behavior in the PR.

Use a Conventional Commit title, describe the problem and resulting behavior,
link related issues, and include validation results and limitations. Keep
credentials, local machine paths, game binaries, saves and build output out
of Git.

For draft release PRs, versioning and installable GitHub release assets, follow
[the release process](docs/releases.md). Authors continue maintaining
`changelog.txt`; merging the release PR is the publication decision.
