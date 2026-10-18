# 2026-10-18 — 2.0 Phase 1: lintheme 1.5.0 with GTK 4 components

- Branch: feat/2.0-gtk4. Kit source: linapptemplate local branch feat/gtk4-components @ 793f9d5.
- How: GLM (GLM-5.3, harness v2, session lmd-gtk4-kit) ported lintheme/gtk3 to lintheme/gtk4
  (~1,500 lines incl. tests and gallery) from a written brief. Its sandbox had no display, so
  it verified with compile/import checks only. Claude audited the trace (2 MEDIUM bookkeeping
  flags, no code impact), ran everything on the real display and fixed:
  1. icons drawn at 16 px whatever was asked (GTK 4 Image ignores texture size) — set_pixel_size;
  2. icons not centred in tiles/hero/empty state (GTK 3 relied on pack expand) — hexpand;
  3. short field hints wrapping per word (GTK 4 wrap labels request min width) — width_chars;
  4. layout mode stuck "compact" after maximizing a narrow window (default-width ignores
     maximize; reproduced at 2560 px) — mode follows size_allocate once mapped, default-width before;
  5. gallery --shot exited silently (window not attached to the Gtk.Application).
- Kit addition: icons.add_icon_dir() + test. Version 1.4.0 -> 1.5.0, kit changelogs updated.
- Verified: kit 50 tests on display; app 131 tests on display, 107 + 22 skipped headless;
  pyflakes + black (110) clean; build_css(3) byte-identical to 1.4.0.
- Files added: lintheme/** (no gtk3), lintheme/VENDORED.md, examples/gallery_gtk4.py,
  resources/icons/phosphor/regular/* (17 SVG + LICENSE-phosphor), ui/__init__.py, ui/icons.py,
  tests/test_kit_{tokens,css,status,gtk4_components,gtk4_shell}.py, tests/test_ui_icons.py
- Files changed: tests/conftest.py, CLAUDE.md, docs/design/GTK4-UPGRADE-PLAN.md, changelog.md,
  .claude/memory/{decisions,pending}.md
