# 2026-10-18 — 2.0 Phase 0: fixed data folder + front-end-neutral jobs module

- Branch: feat/2.0-gtk4 (1.x frozen: tag v1.0.0, branch release/1.x)
- Root cause (paths): 1.x built data/, logs/, downloads/, backups/ from os.getcwd() or
  os.path.abspath('data'), so the working directory decided where history lived. Seen live
  on 2026-10-18: running the 1.x test suite from the repo created data/links_history.json
  full of example.com links, plus logs/, downloads/, backups/.
- Fix: modules/config/paths.py (XDG data dir, LMD_DATA_DIR override, copy-only migration
  with marker, legacy ./downloads still scanned); tests/conftest.py isolates tests.
- Refactor: modules/download/jobs.py takes the download/queue/cancel logic out of
  routes/api.py (routes now only translate HTTP). Behaviour change: an empty output_dir now
  falls back to the default download folder instead of being passed through as "".
- Also: settings.links_history is loaded and trimmed in place (it was rebound, which breaks
  references imported by other modules — the same bug class as the 2026-07-31 cancel flag).
- Tests: 79 -> 92, all pass; pyflakes clean on changed files (app.py's unused `window`
  import predates this change; app.py is replaced in Phase 2).
- Files added: modules/config/paths.py, modules/download/jobs.py, tests/conftest.py,
  tests/test_paths_jobs.py, docs/design/mockups-gtk4/README.md, docs/design/mockups-gtk4/images/*.png
- Files changed: modules/config/{settings,user_settings,logging_config}.py,
  modules/download/dedupe.py, modules/playlists.py, modules/routes/api.py, browser_app.py,
  README.md, DOCUMENTATION.md, ROADMAP.md, CLAUDE.md, docs/design/GTK4-UPGRADE-PLAN.md,
  docs/design/mockups-gtk4/Library.dc.html, changelog.md, .claude/memory/{decisions,pending}.md
