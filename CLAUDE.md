# Project: Linux Media Downloader — CLAUDE.md (v2026.04 — Claude Code Native)

## Overview
A localhost desktop application for downloading YouTube media (audio/video, single
videos or full playlists) for personal, non-commercial use (see LICENSE). A Flask
backend serves a small web UI rendered either in a native PyWebView window
(`app.py`) or an ordinary browser (`browser_app.py`). All downloading is delegated
to `yt-dlp`.

## Architecture
- Language/Framework: Python 3.8+ / Flask (blueprints) + PyWebView (native shell)
- Build system: none (interpreted); Debian `.deb` via `packaging/build-deb.sh`,
  one-command install via `install.sh`, optional AppImage staging under `AppDir/`
- Key dependencies: `Flask`, `yt-dlp`, `pywebview` (see `requirements.txt`)
- Entry points:
  - `app.py` — native window: Flask on an ephemeral localhost port in a thread,
    then a PyWebView window pointed at it.
  - `browser_app.py` — browser fallback: Flask on `127.0.0.1:5000`.
- Modules:
  - `modules/config/settings.py` — config, shared mutable state (`current_download`,
    `download_queue`, `download_history`, `links_history`), history persistence, and
    cancellation accessors (`request_cancel` / `reset_cancel` / `is_cancel_requested`).
  - `modules/config/user_settings.py` — user-editable filler words + character
    replacements that drive text-control operations.
  - `modules/config/logging_config.py` — centralized logging (console + rotating
    `logs/app.log`); `setup_logging()` + `YTDLPLogger`.
  - `modules/download/media.py` — `yt-dlp` orchestration, progress hook, the
    one-at-a-time download queue (`enqueue_download` → job dict → worker), height-
    capped video format selection.
  - `modules/download/chapters.py` — split one long video into per-chapter files.
  - `modules/download/dedupe.py` — record/skip previously-downloaded items.
  - `modules/playlists.py` — manage downloaded playlist folders (list/rename/bulk ops).
  - `modules/routes/api.py` — JSON API blueprint (`/api/*`).
  - `modules/routes/ui.py` — page-rendering blueprint (`/`, `/backups`, `/pending`,
    `/settings`, `/player`, `/file-manager`, `/faq`, ...).
  - `modules/utils/file_utils.py` — filename sanitization, open-folder via xdg-open.
- State model: download state lives in module-level singletons in `settings.py`
  (`current_download` dict, list singletons). These are **mutable and imported by
  reference**, so cross-module mutation works. Scalar flags (e.g. the cancel flag)
  MUST be accessed through the accessor functions, never imported by value.
- Persistence: one data folder, `~/.local/share/linmediadownloader` (`modules/config/paths.py`;
  `LMD_DATA_DIR` overrides). Never write data relative to the cwd or the code folder.
- Upgrade in progress: 2.0 native GTK 4 rewrite on `feat/2.0-gtk4` — docs/design/GTK4-UPGRADE-PLAN.md.
  Download/queue commands for any front end: `modules/download/jobs.py`.
- UI kit: vendored `lintheme/` 1.5.0 (GTK 4 only; see lintheme/VENDORED.md). Never hard-code a colour:
  tokens only. App-only icons: `resources/icons/phosphor/regular/` + `ui/icons.py` (list every used icon in USED).

## Build & Runtime Standards (Enforced)
```
# Build
# (none — pure Python)

# Test (offline; tests/conftest.py isolates the data folder). GTK 4 tests need a display
# (desktop session or xvfb-run -a) and skip without one.
GSK_RENDERER=cairo venv/bin/python -m pytest -q
# Import / syntax check
python3 -c "import modules.config.settings, modules.download.media, modules.routes.api, modules.routes.ui; print('import OK')"
python3 -m py_compile app.py browser_app.py modules/**/*.py

# Lint
python3 -m pyflakes modules app.py browser_app.py   # if installed

# Run (browser mode — works headless)
python3 browser_app.py        # then open http://127.0.0.1:5000

# Run (desktop mode — needs a display + a PyWebView GTK/WebKit2 backend)
python3 app.py
```
- Use `/plan-first` for complex features or multi-file changes.
- Use `/build-test` to run the full pipeline.
- The venv MUST be created with `--system-site-packages` so PyWebView can import the
  system GTK/WebKit2 backend (see `.claude/memory/decisions.md`). Downloads require
  `ffmpeg` (for audio extraction / video+audio merge).

## Project Conventions
- Module-level comment header (`# modules/...`) at the top of each file.
- Modules are Flask blueprints registered in the entry-point files.
- API handlers return `jsonify(...)`; tolerate missing/invalid JSON bodies.
- Shared runtime state is centralized in `modules/config/settings.py`.
- **Never** import a scalar global (like the cancel flag) by value across modules —
  reassigning it in one module will not be seen by the others. Use the accessor
  functions. Mutable shared state (dicts/lists) may be imported by reference.
- Use `logging` (per-module `lmd.*` loggers), never `print()`.

## Sector-Specific Rules
@.claude/rules/ for all active rules (path-scoped via YAML `paths:` frontmatter)

## Memory & Workflow
- Use official Auto Memory (`/memory`) for Claude's own learnings across sessions.
- Human-readable history supplements Auto Memory:
  - Session logs: `.claude/memory/sessions/`
  - Change manifests: `.claude/memory/changes/`
  - Decision log: `.claude/memory/decisions.md`
  - Pending items: `.claude/memory/pending.md`
  - Memory index: `.claude/memory/MEMORY.md`
  - Local change log: `changelog.md` (git-independent, append-only)
- End every significant session with `/session-end` or the session-end checklist.
- Update `changelog.md` as changes are made, not after.

## Hooks (Automated)
Lifecycle hooks are configured in `.claude/settings.json`:
- **SessionStart**: injects pending items, last session log, and recent changelog.
- **PreToolUse**: security gate blocks secret-file access and destructive commands.
- **PostToolUse**: auto-lint/format after file edits (Python section enabled).
- Subagent/Teammate/Task lifecycle hooks for multi-agent runs.

## Custom Commands
- `/plan-first` — plan complex tasks before executing.
- `/build-test` — run the full build + test pipeline from this file.
- `/session-end` — end-of-session wrap-up and logging.
- `/route`, `/team` — intensity routing + multi-agent coordination.

## References
- @.claude/rules/ for path-scoped rules
- @.claude/memory/decisions.md for architectural decision history
- README.md for user-facing feature documentation
