# Development checks

The lightweight CI follows the merged tooling work in
[Quinityn PR #10](https://github.com/jatmn/yuoki-quinityn/pull/10) and
[PR #11](https://github.com/jatmn/yuoki-quinityn/pull/11), adapted for standalone
Yuoki. It runs on pull requests and pushes to `main` and `release/1.3.0`. The dispatcher reads the
complete Git diff and calls only affected reusable workflows. It avoids
GitHub's capped event path filters, does not duplicate runs on topic-branch
pushes, and cancels superseded runs for the same PR. Each branch push has a
separate concurrency group so a later documentation-only push cannot cancel
an earlier push's full Lua checks. The router is loaded from the
comparison revision, so edits to the PR's router cannot disable their own
validation. Initial installation runs all checks when that revision has no router.
A final `CI result` job always runs and fails if any selected check failed or was
cancelled; it is the stable check name to require in branch rules, because routed
jobs are reported under different names when they run or are skipped.

## Which checks run

| Changed surface | Checks |
| --- | --- |
| Shipped Lua | Lua syntax, Luacheck, StyLua and packaging |
| Test-only Lua | Lua checks |
| Python or `.ruff.toml` | Python AST syntax, Ruff lint and CI/Pullfrog/package regressions |
| Release Please config, hidden manifest or version file | Python checks, including release-input contract validation |
| Pullfrog helper or its tests | Python checks and actionlint |
| Package builder or validator | Python checks and packaging |
| Metadata, locale, graphics and other shipped files | Packaging |
| `.luacheckrc` or `.stylua.toml` | Lua checks/configuration probes |
| A workflow | actionlint, Python regressions and the affected validation workflow |
| Dispatcher (`ci.yml`) or `tools/ci_changes.py` | All four workflows |
| `docs/` or `CONTRIBUTING.md` | Change detection only |

The README, changelog and license/acknowledgment files ship, so changes to them
select packaging. Mixed changes run the union of checks. Renames consider both
old and new paths; deletions select their affected surface. Missing comparison
revisions fail CI. The change job also checks diff whitespace.

Lua checks use **Lua 5.2**, **Luacheck 1.2.0**, and **StyLua 2.5.2**. They check
added/modified Lua files on PRs, including renamed files and regular-file/symlink
type changes. Relevant pushes to `main` and `release/1.3.0`, and PRs that change
`.luacheckrc`, `.stylua.toml` or `.github/workflows/lua.yml`, check all tracked Lua
files so lint, formatter or tool-version changes are validated against the baseline. Deleted Lua
files are excluded from the manifest. Configuration is parsed even when no Lua
files changed.
Filenames are passed as NUL-delimited data rather than shell source.

The repository-wide baseline from
[issue #15](https://github.com/jatmn/Yuoki-Factorio-2.x/issues/15) is complete on
`release/1.3.0`. Unrelated documentation/Python changes still do not select Lua.
Factorio stage globals and intentional shared Yuoki exports are declared in
`.luacheckrc`. The sole warning exemption is attached to the deliberately disabled
legacy achievement definition; unknown globals and other warnings remain errors.

The baseline uses StyLua AST verification and matching normalized Lua 5.2
instructions/constants for the mechanical formatting. Separate lint cleanup
removes overwritten connector literals and obsolete nil-valued prototype fields,
unused resource code and an unused local item list. Unused helper parameters keep
their argument positions. Real Factorio 2.1.21 prototype dumps are compared before
and after cleanup, both with base and with Space Age. These checks preserve the
effective prototype definitions; they do not test every third-party mod combination.

## Local commands

Install the versions above plus **actionlint 1.7.12**, **Ruff 0.17.3** and Python 3. Run from the
repository root, substituting your changed Lua paths:

```sh
git diff --check
luac5.2 -p .luacheckrc
luac5.2 -p control.lua
luacheck control.lua
stylua --config-path .stylua.toml control.lua
stylua --check --config-path .stylua.toml control.lua
actionlint
ruff check --config .ruff.toml tools
python3 tools/test_ci_changes.py
python3 tools/test_pullfrog_command.py
python3 tools/test_package.py
python3 tools/package.py
python3 tools/validate_package.py
```

Python CI parses every tracked `.py` file with `ast.parse` without importing
game code, then lints them with Ruff's default correctness rules from `.ruff.toml`
(syntax errors, undefined names, unused imports/variables; no style rules). Its syntax block in `.github/workflows/python.yml` can also be run
locally. Routing regressions use real Git histories, including a Lua change
after 3,500 documentation files, unusual filenames, renames, deletions,
missing revisions, router self-disable attempts, and both file-type transition
directions on both events. Lua CI runs the focused file-selection and compiler
tests even on Lua-workflow-only changes, including filenames beginning with `-`.
Every workflow edit retains the existing Pullfrog authorization regression gate;
Pullfrog helper edits also retain workflow linting.

## Installable package

`tools/package.py` builds `build/dist/Yuoki_<version>.zip` and `SHA256SUMS` from
tracked release sources. Ordering, timestamps and file modes are deterministic.
It preserves `Licence.txt`, `! Thank You !.txt`, gameplay sources, migrations,
locale and graphics. It excludes hidden files, developer docs/tools/tests,
contributor/agent guidance and generated output. Untracked files never ship;
stage new release files before building a local development ZIP. Both package
tools require regular source files contained within the checkout, including
metadata, and reject symlinks, backslashes, drive prefixes and traversal paths.
The builder checks the mod name and version against the validator's rules
before deriving or opening the output ZIP, so malformed metadata cannot
overwrite files outside the requested output directory.

The validator checks metadata, the versioned archive root, exact tracked
release membership and bytes, required entrypoints and notices, CRC integrity
and the SHA256 checksum. Python CI also tests source escapes and archive-path
safety through both real tools. CI attaches the ZIP/checksum for seven days;
reruns replace the same run's artifact. It does not publish releases or change
mod versions.

CI has read-only contents permissions and downloads no Factorio binaries or
dependency mods. These checks do not prove game API compatibility, save
migration, recipe correctness, graphics or gameplay. Engine validation remains
local and must use the appropriate Factorio/mod versions for behavioral work.
The separate [Pullfrog workflow](pullfrog.md) retains its owner-command policy.
