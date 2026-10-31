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
git ls-files -z -- '*.py' | xargs -0 -r ruff check --config .ruff.toml --
python3 tools/test_ci_changes.py
python3 tools/test_pullfrog_command.py
python3 tools/test_package.py
python3 tools/package.py
python3 tools/validate_package.py
```

Python CI parses every tracked `.py` file with `ast.parse` without importing
game code, then lints them with Ruff's correctness rules from `.ruff.toml` (E9 + Pyflakes)
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

## Factorio 2.1.24 regression scenario

`tests/factorio/control.lua` runs the production migration helpers against real
engine stacks, inventories, filters, logistics, circuits and connected fluids.
It also checks quality energy multipliers, the pump module slot, and all ten
generators below and above their minimum input temperatures. Failures produce
`FAIL` log lines and a failing test result. Run with base + Yuoki, then repeat
with Quality, Space Age + Quality, and Space Age without Quality.

Build the package above, then use an isolated Factorio write-data directory:

```sh
# Set these to the installed 2.1.24 executable and its data directory.
FACTORIO_BIN=/path/to/factorio/bin/x64/factorio
FACTORIO_DATA=/path/to/factorio/data
TEST_DIR=$(mktemp -d)
mkdir -p "$TEST_DIR/mods" "$TEST_DIR/scenarios/yuoki-regression"
cp build/dist/Yuoki_*.zip "$TEST_DIR/mods/"
cp tests/factorio/control.lua "$TEST_DIR/scenarios/yuoki-regression/"
cat > "$TEST_DIR/config.ini" <<EOF
[path]
read-data=$FACTORIO_DATA
write-data=$TEST_DIR
EOF
cat > "$TEST_DIR/mods/mod-list.json" <<'EOF'
{"mods":[{"name":"base","enabled":true},{"name":"Yuoki","enabled":true},
{"name":"quality","enabled":false},{"name":"space-age","enabled":false},
{"name":"recycler","enabled":false},{"name":"elevated-rails","enabled":false}]}
EOF
"$FACTORIO_BIN" -c "$TEST_DIR/config.ini" --mod-directory "$TEST_DIR/mods" \
  --test-scenario yuoki-regression --test-ticks 241
```

Enable the appropriate official mods in `mod-list.json` for each additional
configuration; include Recycler with Quality, and Elevated Rails with Space Age.
The scenario is developer-only and is excluded from the release ZIP. It does
not replace saved-game upgrade testing or validation of third-party mod packs.

`tests/factorio/migration-fixture/` is a developer-only mod for testing the
`1.3.1.lua` follow-up on saves that already recorded `1.2.21.lua`. Use it only in
an isolated mod directory: it supplies a minimal `angels-slag` item. Create the
write-data `saves/` directory first. Bind the server to localhost and disable public
and LAN visibility in its settings. Seed a save
with Yuoki before the vehicle/corpse scan fix, then load it with `--start-server`
and `auto_pause: false` in the server settings. The fixture verifies the omitted
inventories, saves `yuoki-old-migration-applied.zip`, and pauses. Stop the server,
then load that save with the repaired
package; it checks counts, quality, existing converted items and unrelated items,
then saves `yuoki-followup-applied.zip` and pauses again. Run the latter with
`--test-save` and at least four test ticks to prove the follow-up does not repeat.
Run with and without Quality; missing/hidden target
variants must leave the original slag untouched. The mod version need not change
for Factorio to discover a newly added migration filename.

Fluid migration checks include empty editable pump/pipe filters and multiple filters on a
shared pipe segment, including a neighboring segment already holding the target
fluid. The helper captures each source segment once, clears its fluid, remaps
editable filters, then adds the converted contents without overwriting existing
target fluid. Empty editable filters migrate independently of contents; empty
fixed recipe/prototype filters retain their machine restrictions. Fixed filters
on storage containing the old fluid must already permit the replacement;
incompatible fixed filters are rejected before any fluid contents change.

For productivity behavior, copy `tests/factorio/productivity.lua` into a separate
scenario's `control.lua` and run it with `--test-ticks 601`. Run both setting
values with the same four official mod configurations. The test asserts module
eligibility and actual crafting: 40 wood yields 20 chests in restricted mode,
or 25 with a Yuoki science module in unrestricted mode; vanilla productivity
modules remain rejected and speed/efficiency modules remain accepted.
For a headless unrestricted run, use a fresh mod directory without
`mod-settings.dat` and a temporary test mod depending on `Yuoki` whose
`settings-updates.lua` contains:

```lua
data.raw["bool-setting"]["yuoki-prod-mod-behaviour"].default_value = false
```

Also repeat the productivity scenario with `tests/factorio/category-fixture/`
copied into the isolated mod directory as `yuoki-category-fixture`, and enable
`yuoki-category-fixture` in `mod-list.json`. Run both setting values. This fixture
gives the Yuoki modules two different original categories and checks that each
machine accepts only its original module family on both restricted and
unrestricted recipes. The fixture is developer-only and does not ship.

The `yuoki-prod-mod-behaviour` startup toggle retains its original polarity:
checked (the default) uses recipe productivity restrictions; unchecked permits
the four Yuoki productivity modules on all recipes in machines that accept them.
Vanilla and other productivity modules retain their recipe eligibility through
module category filters. Machine effect/category restrictions, productivity
caps and products excluded from productivity remain in force. A shared category
containing both productivity and non-productivity modules is split so the
non-productivity modules retain access. Mods that rewrite these prototypes after
Yuoki's final-fixes stage may need integration adjustments.

**Before re-enabling restrictions in an existing save, remove Yuoki productivity
modules from machines using recipes that normally reject productivity.** Factorio
removes newly incompatible installed modules during prototype fixup, before
`on_configuration_changed` or migration scripts can recover them. This was
reproduced by loading the same save with each setting value; there is no recovery
inventory for those modules. Disabling restrictions does not require this step.

Replacement stacks that exceed the new item's stack size spill the excess next
to their owner, preserving count and quality rather than discarding items.

## Washer save and recipe regression

`tests/factorio/washer-fixture/` checks the washer fluid-layout upgrade on real
2.1.24 saves. It requires Yuoki Engines. Copy the fixture into an isolated mod
directory as `yuoki-washer-fixture`. With Yuoki before the washer fix, create a
save using `--create /absolute/path/washer-seed.zip`. The fixture seeds both
washers with every owned single-fluid washing recipe, all four orientations,
normal/rare quality where available, installed modules, input/output items,
full fluid buffers at 75°C, and pipes on both sides.

Replace Yuoki with the repaired package and change the isolated fixture's
`info.json` version from `1.0.0` to `1.0.1` to trigger its verification callback.
Load the seed using `--test-save /absolute/path/washer-seed.zip --test-ticks 301`.
The fixture asserts unchanged recipes, item counts/quality, fluid amounts and
temperatures, buffer capacities and pipe connections. It then runs Engines'
acid-neutralization recipe through physical pipes in both washers and every
orientation/quality, requiring exactly 20 contaminated water and 9 mechanical
force. Each physical output port must carry its designated fluid and quantity;
the expected side is rotated with the machine, independently of recipe filters.
Swapping the two output connections must fail this check even when total output
amounts are unchanged. Successful logs include `WASHER_PRESERVED` and `WASHER_PASS`.

Repeat with base, Quality + Recycler, Space Age + Quality + Recycler + Elevated
Rails, and Space Age + Recycler + Elevated Rails without Quality. Repeating the
upgrade against the old Yuoki package preserves the seed but fails acid recipe
selection. No fixture, save or game binary ships in the mod ZIP.

The washers have two independent inputs and outputs. Existing single-fluid
recipes explicitly select the first box and optionally share the second; this
preserves both existing ports and saved fluid storage. Relying on automatic
merging after changing the prototype layout clears saved internal fluids in
2.1.24. Each independent box has volume 100, preserving the previous combined
volume 200 per side and the existing recipe-derived buffer capacities. No Lua
save migration or entity replacement is needed.
