# Vendored copy of lintheme

Copied, not referenced (universal instruction set: copy, don't reference), from
[LinAppTemplate](https://github.com/MensuraMedia/linapptemplate).

| | |
|---|---|
| Kit version | 1.5.3 |
| Source | linapptemplate `feat/gtk4-components` at `0a4e687` (built for this app on 2026-10-18; not merged upstream yet) |
| Left out | `lintheme/gtk3/` (this app is GTK 4 only) |
| App changes | `tokens.COLOR['focus']` is the accent blue `#4c9dff`, not the kit's yellow (user, 2026-10-18: no yellow borders); otherwise none inside `lintheme/`; app-only icons live in `resources/icons/phosphor/regular/` and are registered with `icons.add_icon_dir()` |

To update: copy the newer `lintheme/` over this one (keep `gtk3/` out), update this table,
run the kit tests (`tests/test_kit_*.py`) and record the version in `.claude/memory/decisions.md`.
