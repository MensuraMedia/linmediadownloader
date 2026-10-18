#!/usr/bin/env python3
# modules/playlists.py
# Discover and manage previously-downloaded playlists (folders with >1 track).

import os
import re
import json
import shutil
import hashlib
import logging
import subprocess
import unicodedata

from modules.config import paths, settings
from modules.utils.file_utils import sanitize_filename

logger = logging.getLogger('lmd.playlists')

# Per-playlist number colors (keyed by folder realpath), persisted in the data directory
COLORS_FILE = paths.data_file('playlist_colors.json')
DEFAULT_COLOR = '#0d6efd'


def load_colors():
    try:
        with open(COLORS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_colors(colors):
    try:
        os.makedirs(os.path.dirname(COLORS_FILE), exist_ok=True)
        with open(COLORS_FILE, 'w') as f:
            json.dump(colors, f, indent=2)
    except Exception as e:
        logger.error('Error saving playlist colors: %s', e)


def _sanitize_color(color):
    color = (color or '').strip()
    return color.lower() if re.fullmatch(r'#[0-9a-fA-F]{6}', color) else DEFAULT_COLOR


def set_playlist_color(path, color):
    """Persist a badge color for a playlist (keyed by its real path)."""
    if not _is_safe_path(path) or not os.path.isdir(path):
        return {'status': 'error', 'message': 'Invalid playlist path'}
    color = _sanitize_color(color)
    colors = load_colors()
    colors[os.path.realpath(path)] = color
    save_colors(colors)
    return {'status': 'success', 'color': color}


# Fixed per-playlist sequence numbers. Each playlist keeps a monotonic "order"
# assigned when it is first seen (newest gets the highest); the displayed badge
# is order % 1000, so it counts 000..999 and wraps back to 000.
SEQ_FILE = paths.data_file('playlist_seq.json')


def load_seq():
    try:
        with open(SEQ_FILE) as f:
            data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get('orders'), dict):
                return {'next': int(data.get('next', 0)), 'orders': data['orders']}
    except Exception:
        pass
    return {'next': 0, 'orders': {}}


def save_seq(seq):
    try:
        os.makedirs(os.path.dirname(SEQ_FILE), exist_ok=True)
        with open(SEQ_FILE, 'w') as f:
            json.dump(seq, f, indent=2)
    except Exception as e:
        logger.error('Error saving playlist sequence: %s', e)

# Media file types we recognize as "tracks"
MEDIA_EXTS = {
    '.mp3', '.m4a', '.mp4', '.webm', '.opus', '.wav',
    '.flac', '.ogg', '.oga', '.mkv', '.aac', '.mov', '.avi',
}

# A "long" file is over 7 minutes
LONG_SECONDS = settings.LONG_SECONDS

# Max characters kept by the "truncate" operation
TRUNCATE_LEN = 35

# Common clutter words stripped by the "remove filler" operation (case-insensitive)
# Filler words are user-editable (Settings page); the effective set comes from
# user_settings. FILLER_WORDS remains the built-in default (used as a fallback).
from modules.config import user_settings
FILLER_WORDS = user_settings.DEFAULT_FILLER_WORDS


def _scan_dirs():
    """Directories that may contain playlist folders (download roots + history)."""
    dirs = set()
    if settings.default_download_path:
        dirs.add(os.path.abspath(settings.default_download_path))
    for entry in settings.download_history:
        out = entry.get('output_dir')
        if not out:
            continue
        out = os.path.abspath(out)
        # Only treat the parent as a scan root when output_dir is an actual
        # "<name>_playlist" folder. Otherwise output_dir IS the download root —
        # using its parent would scan the whole home directory. (A playlist URL
        # grabbed in single mode records is_playlist=True but a non-playlist
        # output_dir, so is_playlist alone is not a reliable signal.)
        if os.path.basename(out).endswith('_playlist'):
            dirs.add(os.path.dirname(out))
        else:
            dirs.add(out)
    # 1.x kept downloads in ./downloads wherever it was launched; keep finding them.
    dirs.update(paths.legacy_download_dirs())
    return {d for d in dirs if os.path.isdir(d)}


def _is_media(name):
    return os.path.splitext(name)[1].lower() in MEDIA_EXTS


def _is_safe_path(path):
    """True only if `path` resolves inside one of the known download directories.

    Guards the destructive rename/delete operations against path traversal.
    """
    if not path:
        return False
    rp = os.path.realpath(path)
    for base in _scan_dirs():
        b = os.path.realpath(base)
        if rp == b or rp.startswith(b + os.sep):
            return True
    return False


def _safe_folder_name(name):
    """Sanitize a user-supplied folder name (allow spaces/brackets, block traversal)."""
    name = (name or '').strip().strip('.')
    name = re.sub(r'[/\\\x00]', '', name)
    return name[:200] or 'playlist'


def _duration(path):
    """Return media duration in seconds via ffprobe, or None if unavailable."""
    try:
        out = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
             '-of', 'csv=p=0', path],
            capture_output=True, text=True, timeout=30,
        )
        return float(out.stdout.strip())
    except Exception:
        return None


def _media_files(path):
    return sorted(
        f for f in os.listdir(path)
        if _is_media(f) and os.path.isfile(os.path.join(path, f))
    )


def list_playlists():
    """Return folders holding more than one media file, newest (by mtime) first."""
    colors = load_colors()
    seen = {}
    for base in _scan_dirs():
        try:
            entries = os.listdir(base)
        except OSError:
            continue
        for name in entries:
            folder = os.path.join(base, name)
            if not os.path.isdir(folder):
                continue
            try:
                files = _media_files(folder)
            except OSError:
                continue
            if len(files) > 1:  # a playlist = more than one song
                rp = os.path.realpath(folder)
                if rp in seen:
                    continue
                size = 0
                for f in files:
                    try:
                        size += os.path.getsize(os.path.join(folder, f))
                    except OSError:
                        pass
                try:
                    mtime = os.path.getmtime(folder)
                except OSError:
                    mtime = 0
                seen[rp] = {
                    'name': name,
                    'path': folder,
                    'file_count': len(files),
                    'total_size': size,
                    'mtime': mtime,
                    'color': colors.get(rp, DEFAULT_COLOR),
                }

    # Assign a fixed, monotonic order to any newly-seen playlist. New ones are
    # numbered oldest→newest by mtime so the most recent gets the highest order.
    seq = load_seq()
    orders = seq['orders']
    new_rps = sorted((rp for rp in seen if rp not in orders),
                     key=lambda rp: seen[rp]['mtime'])
    if new_rps:
        for rp in new_rps:
            orders[rp] = seq['next']
            seq['next'] += 1
        save_seq(seq)

    for rp, info in seen.items():
        info['order'] = orders.get(rp, 0)
        info['seq'] = info['order'] % 1000  # 000..999, wraps

    # Latest-added (highest order) first.
    return sorted(seen.values(), key=lambda x: x['order'], reverse=True)


def list_playlist_files(path):
    """List a playlist's media files with duration and size, or None if invalid."""
    if not _is_safe_path(path) or not os.path.isdir(path):
        return None
    files = []
    for name in _media_files(path):
        fp = os.path.join(path, name)
        try:
            size = os.path.getsize(fp)
        except OSError:
            size = 0
        files.append({
            'filename': name,
            'size': size,
            'duration': _duration(fp),
        })
    return files


def rename_playlist(path, new_name):
    """Rename the playlist folder on disk."""
    if not _is_safe_path(path) or not os.path.isdir(path):
        return {'status': 'error', 'message': 'Invalid playlist path'}
    new_name = _safe_folder_name(new_name)
    parent = os.path.dirname(os.path.abspath(path))
    new_path = os.path.join(parent, new_name)
    if os.path.realpath(new_path) == os.path.realpath(path):
        return {'status': 'success', 'path': path, 'name': new_name}
    if os.path.exists(new_path):
        return {'status': 'error', 'message': 'A folder with that name already exists'}
    try:
        os.rename(path, new_path)
    except OSError as e:
        return {'status': 'error', 'message': str(e)}
    old_rp = os.path.realpath(path)
    new_rp = os.path.realpath(new_path)
    # Carry the badge color over to the new path
    colors = load_colors()
    if old_rp in colors:
        colors[new_rp] = colors.pop(old_rp)
        save_colors(colors)
    # Carry the fixed sequence number over too
    seq = load_seq()
    if old_rp in seq['orders']:
        seq['orders'][new_rp] = seq['orders'].pop(old_rp)
        save_seq(seq)
    return {'status': 'success', 'path': new_path, 'name': new_name}


def delete_long_files(path, max_seconds=LONG_SECONDS, record=True):
    """Move media files longer than max_seconds into a .trash folder (undoable)."""
    if not _is_safe_path(path) or not os.path.isdir(path):
        return {'status': 'error', 'message': 'Invalid playlist path'}
    trash = os.path.join(path, '.trash')
    moves = []
    for name in _media_files(path):
        fp = os.path.join(path, name)
        dur = _duration(fp)
        if dur is not None and dur > max_seconds:
            os.makedirs(trash, exist_ok=True)
            dst = os.path.join(trash, _unique_name(trash, name, name))
            try:
                os.rename(fp, dst)
                moves.append((fp, dst))
            except OSError:
                pass
    if record:
        _record(moves)
    return {'status': 'success', 'deleted': len(moves), 'moves': moves, **stack_state()}


def trash_count(path):
    """Number of files currently sitting in a playlist's .trash folder."""
    trash = os.path.join(path, '.trash')
    if not os.path.isdir(trash):
        return 0
    try:
        return sum(1 for f in os.listdir(trash) if os.path.isfile(os.path.join(trash, f)))
    except OSError:
        return 0


def empty_trash(path):
    """Permanently delete a playlist's .trash folder (not undoable)."""
    if not _is_safe_path(path) or not os.path.isdir(path):
        return {'status': 'error', 'message': 'Invalid playlist path'}
    trash = os.path.join(path, '.trash')
    if not os.path.isdir(trash):
        return {'status': 'success', 'purged': 0}
    purged = trash_count(path)
    try:
        shutil.rmtree(trash)
    except OSError as e:
        return {'status': 'error', 'message': str(e)}
    return {'status': 'success', 'purged': purged}


# ── Undo / redo ──────────────────────────────────────────────────────────────
# Each recorded op is a list of (src, dst) moves that were performed. Undo
# reverses them; redo replays them. State is in-memory (resets on restart).
_undo_stack = []
_redo_stack = []


def stack_state():
    return {'can_undo': bool(_undo_stack), 'can_redo': bool(_redo_stack)}


def _record(moves):
    if moves:
        _undo_stack.append(moves)
        _redo_stack.clear()


def _safe_move(src, dst):
    if not (_is_safe_path(src) and _is_safe_path(os.path.dirname(dst))):
        return False
    if os.path.exists(dst):
        return False
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        os.rename(src, dst)
        return True
    except OSError:
        return False


def _apply_moves(moves):
    return sum(1 for src, dst in moves if _safe_move(src, dst))


def undo_last():
    """Reverse the most recent operation."""
    if not _undo_stack:
        return {'status': 'noop', **stack_state()}
    moves = _undo_stack.pop()
    changed = _apply_moves([(dst, src) for (src, dst) in reversed(moves)])
    _redo_stack.append(moves)
    return {'status': 'success', 'changed': changed, **stack_state()}


def redo_last():
    """Replay the most recently undone operation."""
    if not _redo_stack:
        return {'status': 'noop', **stack_state()}
    moves = _redo_stack.pop()
    changed = _apply_moves(moves)
    _undo_stack.append(moves)
    return {'status': 'success', 'changed': changed, **stack_state()}


def _unique_name(path, new_name, original):
    """Return new_name, inserting a 4-char salt before the extension on collision."""
    if not os.path.exists(os.path.join(path, new_name)):
        return new_name
    base, ext = os.path.splitext(new_name)
    salt = hashlib.md5(original.encode('utf-8', 'ignore')).hexdigest()[:4]
    candidate = f"{base}_{salt}{ext}"
    n = 1
    while os.path.exists(os.path.join(path, candidate)):
        candidate = f"{base}_{salt}{n}{ext}"
        n += 1
    return candidate


def _rename_within(path, mapper, record=True):
    """Apply mapper(base_name, index) -> new_base to each media file.

    On a name collision a 4-character salt is inserted before the extension so
    uniqueness is always preserved (rather than skipping the file). When
    `record` is False the moves are returned but not pushed to the undo stack
    (used by global operations that record all folders as one undo entry).
    """
    if not _is_safe_path(path) or not os.path.isdir(path):
        return {'status': 'error', 'message': 'Invalid playlist path'}
    moves = []
    for idx, name in enumerate(_media_files(path)):
        base, ext = os.path.splitext(name)
        new_base = (mapper(base, idx) or '').strip() or base
        new_name = new_base + ext
        if new_name == name:
            continue
        new_name = _unique_name(path, new_name, name)
        src = os.path.join(path, name)
        dst = os.path.join(path, new_name)
        try:
            os.rename(src, dst)
            moves.append((src, dst))
        except OSError:
            pass
    if record:
        _record(moves)
    return {'status': 'success', 'renamed': len(moves), 'moves': moves, **stack_state()}


def _split_camel(token):
    """Split a CamelCase / PascalCase token into its words (e.g. OfficialVideo)."""
    parts = re.findall(r'[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+', token)
    return parts or [token]


def _is_filler_word(word):
    low = word.lower()
    return low in user_settings.get_filler_words() or bool(re.fullmatch(r'(?:19|20)\d{2}', low))


def _apply_replacements(base):
    """Apply the user's configured character/string replacements to a name."""
    for frm, to in user_settings.get_char_replacements():
        base = base.replace(frm, to)
    return base


def _remove_filler(base):
    """Drop clutter words (filler + years) — even when glued together in camelCase.

    e.g. "Artist - Song (Official Music Video) [4K HD]" -> "Artist Song"
         "SongTitleOfficialVideo"                       -> "SongTitle"
    """
    out = []
    for tok in re.split(r'[\s_\-\[\]\(\)\{\}]+', base):
        if not tok:
            continue
        # Whole-token match first so units like "4K"/"HD" and years are caught
        # before camelCase splitting breaks them apart.
        whole = re.sub(r'[^\w]', '', tok)
        if whole and _is_filler_word(whole):
            continue
        kept = [s for s in _split_camel(tok) if not _is_filler_word(s)]
        if kept:
            out.append(''.join(kept))
    return ' '.join(out).strip()


def _to_standard(base):
    """Normalize fancy / accented / full-width characters to standard ASCII."""
    norm = unicodedata.normalize('NFKD', base)
    return norm.encode('ascii', 'ignore').decode('ascii').strip()


def _title_case(base):
    # Capitalize the first letter of every word, including after separators like
    # _ - . spaces and digits (so brad_fiedel_the_terminator -> Brad_Fiedel_The_Terminator).
    return re.sub(r'(^|[^A-Za-z])([a-z])',
                  lambda m: m.group(1) + m.group(2).upper(),
                  base.lower())


def _camel_case(base):
    words = [w for w in re.split(r'[\s_\-]+', base) if w]
    return ''.join(w[:1].upper() + w[1:].lower() for w in words)


def abbreviate_duplicate_strings(path, keep=4, record=True):
    """Shorten tokens that recur across many files to their first `keep` chars.

    e.g. a playlist where every file starts "Predator_Soundtrack_" becomes
    "Pred_Soun_<unique part>" — the repeated words are abbreviated, the unique
    per-track parts are left intact.
    """
    if not _is_safe_path(path) or not os.path.isdir(path):
        return {'status': 'error', 'message': 'Invalid playlist path'}

    mapper = _abbreviate_mapper(path, keep)
    if mapper is None:
        if record:
            _record([])
        return {'status': 'success', 'renamed': 0, 'moves': [], **stack_state()}
    return _rename_within(path, mapper, record=record)


def _abbreviate_mapper(path, keep=4):
    """The abbreviate-duplicates mapper for this folder, or None when nothing recurs"""
    bases = [os.path.splitext(f)[0] for f in _media_files(path)]

    # How many files each token appears in (case-insensitive, once per file)
    freq = {}
    for base in bases:
        for low in {t.lower() for t in re.split(r'[\s_\-]+', base) if t}:
            freq[low] = freq.get(low, 0) + 1

    # "Duplicate" = recurs in 2+ files and is long enough that abbreviating helps
    common = {tok for tok, count in freq.items() if count >= 2 and len(tok) > keep}
    if not common:
        return None

    def mapper(base, idx):
        parts = re.split(r'([\s_\-]+)', base)  # keeps delimiters at odd indices
        return ''.join(
            part[:keep] if (i % 2 == 0 and part.lower() in common) else part
            for i, part in enumerate(parts)
        )

    return mapper


def is_safe_path(path):
    """Public guard: True if path resolves inside a known download root."""
    return _is_safe_path(path)


def list_all_media():
    """Every downloaded media file across the download roots (for the Player)."""
    seen = set()
    out = []
    for base in _scan_dirs():
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if not d.startswith('.')]  # skip .trash etc.
            for name in files:
                if not _is_media(name):
                    continue
                full = os.path.join(root, name)
                rp = os.path.realpath(full)
                if rp in seen:
                    continue
                seen.add(rp)
                try:
                    size = os.path.getsize(full)
                except OSError:
                    size = 0
                out.append({
                    'name': name,
                    'path': full,
                    'folder': os.path.basename(root),
                    'size': size,
                })
    return sorted(out, key=lambda x: (x['folder'].lower(), x['name'].lower()))


def delete_media_file(path):
    """Move a single media file to its folder's .trash (recoverable delete)."""
    if not _is_safe_path(path) or not os.path.isfile(path):
        return {'status': 'error', 'message': 'Invalid file path'}
    trash = os.path.join(os.path.dirname(path), '.trash')
    os.makedirs(trash, exist_ok=True)
    base = os.path.basename(path)
    dst = os.path.join(trash, _unique_name(trash, base, base))
    try:
        os.rename(path, dst)
        return {'status': 'success'}
    except OSError as e:
        return {'status': 'error', 'message': str(e)}


def add_to_folder(path, folder_name):
    """Copy a media file into a (new) folder under the download root — curation."""
    if not _is_safe_path(path) or not os.path.isfile(path):
        return {'status': 'error', 'message': 'Invalid file path'}
    name = _safe_folder_name(folder_name)
    if not name:
        return {'status': 'error', 'message': 'Folder name required'}
    root = os.path.abspath(settings.default_download_path or 'downloads')
    dest_dir = os.path.join(root, name)
    os.makedirs(dest_dir, exist_ok=True)
    base = os.path.basename(path)
    dst = os.path.join(dest_dir, _unique_name(dest_dir, base, base))
    try:
        shutil.copy2(path, dst)
        return {'status': 'success', 'folder': dest_dir, 'name': name}
    except OSError as e:
        return {'status': 'error', 'message': str(e)}


def apply_operation(path, operation, record=True):
    """Dispatch a bulk file operation over a playlist folder."""
    if not _is_safe_path(path) or not os.path.isdir(path):
        return {'status': 'error', 'message': 'Invalid playlist path'}

    if operation == 'delete_long':
        return delete_long_files(path, record=record)
    if operation == 'abbreviate_dupes':
        return abbreviate_duplicate_strings(path, record=record)

    mapper = _mapper_for(path, operation)
    if mapper is None:
        return {'status': 'error', 'message': f'Unknown operation: {operation}'}
    return _rename_within(path, mapper, record=record)


# The text mappers shared by apply_operation and preview_operation.
# Each takes (base_name, file_index) and returns the new base name.
_RENAME_OPS = {
    'remove_special': lambda b, i: re.sub(r'[^\w\s.-]', '', b).strip(),
    'replace_spaces': lambda b, i: re.sub(r'\s+', '_', b.strip()),
    # Full clean: strip specials, collapse spaces/dashes to underscores.
    'clean':          lambda b, i: os.path.splitext(sanitize_filename(b + '.x'))[0],
    'truncate':       lambda b, i: b[:TRUNCATE_LEN].strip(),
    'remove_filler':  lambda b, i: _remove_filler(b),
    'apply_replacements': lambda b, i: _apply_replacements(b),
    'standard_font':  lambda b, i: _to_standard(b),
    'lower_case':     lambda b, i: b.lower(),
    'upper_case':     lambda b, i: b.upper(),
    'title_case':     lambda b, i: _title_case(b),
    'camel_case':     lambda b, i: _camel_case(b),
}


def _mapper_for(path, operation):
    """The rename mapper for an operation (number_prefix included), or None"""
    if operation in _RENAME_OPS:
        return _RENAME_OPS[operation]
    if operation == 'number_prefix':
        width = max(2, len(str(len(_media_files(path)))))
        return lambda b, i: f"{str(i + 1).zfill(width)}_{re.sub(r'^[0-9]+[_-]', '', b)}"
    return None


def _planned_unique(new_name, original, taken):
    """The preview's guess at _unique_name: salt a planned name that collides"""
    if new_name not in taken:
        return new_name
    base, ext = os.path.splitext(new_name)
    salt = hashlib.md5(original.encode('utf-8', 'ignore')).hexdigest()[:4]
    candidate = f'{base}_{salt}{ext}'
    n = 1
    while candidate in taken:
        candidate = f'{base}_{salt}{n}{ext}'
        n += 1
    return candidate


def preview_operation(path, operation):
    """[(old, new)] for an operation, without touching any file (the Tidy names
    preview). For delete_long the new name is the file's trash path. The real run
    may salt a name differently if renames collide mid-run."""
    if not _is_safe_path(path) or not os.path.isdir(path):
        return []
    files = _media_files(path)
    if operation == 'delete_long':
        planned = []
        for name in files:
            duration = _duration(os.path.join(path, name))
            if duration is not None and duration > LONG_SECONDS:
                planned.append((name, os.path.join('.trash', name)))
        return planned
    mapper = _abbreviate_mapper(path) if operation == 'abbreviate_dupes' else _mapper_for(path, operation)
    if mapper is None:
        return []
    taken = set(files)
    planned = []
    for index, name in enumerate(files):
        base, ext = os.path.splitext(name)
        new_name = ((mapper(base, index) or '').strip() or base) + ext
        if new_name == name:
            continue
        new_name = _planned_unique(new_name, name, taken)
        taken.add(new_name)
        planned.append((name, new_name))
    return planned


def preview_global(operation):
    """preview_operation across every app folder (the All files view), as one list"""
    planned = []
    for playlist in list_playlists():
        planned.extend(preview_operation(playlist['path'], operation))
    return planned



# ── File Manager (app-recorded files) ────────────────────────────────────────
def list_app_media():
    """Media files inside the app's playlist folders — files this app recorded.

    Narrower than list_all_media(): only folders the app created/uses, not every
    loose file in the download root.
    """
    out = []
    seen = set()
    for pl in list_playlists():
        folder = pl['path']
        try:
            files = _media_files(folder)
        except OSError:
            continue
        for name in files:
            full = os.path.join(folder, name)
            rp = os.path.realpath(full)
            if rp in seen:
                continue
            seen.add(rp)
            try:
                size = os.path.getsize(full)
            except OSError:
                size = 0
            out.append({'name': name, 'path': full, 'folder': pl['name'], 'size': size})
    return sorted(out, key=lambda x: (x['folder'].lower(), x['name'].lower()))


def file_stats():
    """Stats over app-recorded files: total, duplicate names, same-size groups."""
    from collections import Counter
    files = list_app_media()
    names = Counter(f['name'].lower() for f in files)
    sizes = Counter(f['size'] for f in files if f['size'] > 0)
    return {
        'total': len(files),
        'duplicate_names': sum(c for c in names.values() if c > 1),
        'same_size': sum(c for c in sizes.values() if c > 1),
    }


def global_operation(operation):
    """Apply a text operation across every app folder as ONE undoable action."""
    folders = sorted({os.path.dirname(f['path']) for f in list_app_media()})
    total = 0
    all_moves = []
    for folder in folders:
        res = apply_operation(folder, operation, record=False)
        if res.get('status') == 'success':
            all_moves.extend(res.get('moves', []))
            total += res.get('renamed', 0) + res.get('deleted', 0)
    _record(all_moves)
    key = 'deleted' if operation == 'delete_long' else 'renamed'
    return {'status': 'success', key: total, 'folders': len(folders), **stack_state()}
