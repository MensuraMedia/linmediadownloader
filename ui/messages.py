# ui/messages.py
"""Every user-visible sentence of the 2.0 Download page (phase 2), in one place.

A test lints each string with lintheme.status.problems(), so no copy may shout,
show a raw error code in a headline, or use a typed arrow. Templates keep their
{placeholders}; the page fills them. Text that is not ours (yt-dlp's raw error
text, file names, titles) is shown as data, never written here.

House pattern for problems: what happened · why · next step (see ERRORS below).
"""

# -- shell ----------------------------------------------------------------------
APP_NAME = "LinMediaDownloader"
PAGE_DOWNLOAD = "Download"
PAGE_ACTIVITY = "Activity"
PAGE_LIBRARY = "Library"
PAGE_SETTINGS = "Settings"
COMING_LATER = "Coming in a later 2.0 phase"

# -- header chip (window.chip.set_status(text, key)) ----------------------------
CHIP_TOOLS_OK = "Ready · yt-dlp and ffmpeg found"
CHIP_TOOLS_NO_YTDLP = "Needs you · yt-dlp is missing"
CHIP_TOOLS_NO_FFMPEG = "Needs you · ffmpeg is missing"
CHIP_READING = "Reading · the link"
CHIP_DOWNLOADING = "Downloading · {i} of {M}"
CHIP_CANT_REACH = "Can't reach · {site}"
# Which browser sign-in yt-dlp uses (modules/download/access.py picks it by itself)
ACCESS_SIGNED_IN = "Signed in to YouTube through {browser}"
ACCESS_NONE = (
    "Not signed in: YouTube may ask to confirm you're not a bot. Signing in in any browser here fixes it."
)
# Finished with nothing saved (every track failed): never shown as a success
DONE_NOTHING = "Nothing was downloaded"
AB_NOTHING = "Nothing was downloaded · {time}"
AB_NOTHING_NO_TIME = "Nothing was downloaded"
RING_A11Y_NOTHING = "Nothing was downloaded"
RETRY_DOWNLOAD = "Try again"
SITE_FALLBACK = "the site"

# -- Link card ------------------------------------------------------------------
CARD_LINK = "Link"
CLEAR = "Clear"
PASTE = "Paste"
LINK_NAME = "Video or playlist link"
LINK_PLACEHOLDER = "Paste a video or playlist link"
READING = "Reading the link…"
PLAYLIST_FOUND = "Playlist found"
VIDEO_FOUND = "Video found"
FOUND_PLAYLIST_DETAIL = "· {title} · {count} videos · {duration}"
FOUND_VIDEO_DETAIL = "· {title} · {duration}"
READ_FAILED = "Couldn't read this link"
READ_FAILED_WHERE = "· see why on the right"
QUEUED_AHEAD = "Queued · {position} ahead"

# -- Format card ----------------------------------------------------------------
CARD_FORMAT = "Format"
FORMAT_NAME = "Format"
FORMAT_AUDIO = "Audio · MP3"
FORMAT_VIDEO = "Video · MP4"
AUDIO_RATE = "192 kbps"
FIELD_QUALITY = "Quality"
QUALITY_NAME = "Video quality"
QUALITY_1080 = "1080p"
QUALITY_720 = "720p"
QUALITY_480 = "480p"

# -- Playlist card --------------------------------------------------------------
CARD_PLAYLIST = "Playlist"
FIELD_GET = "Get"
GET_NAME = "How much of the playlist"
GET_THIS_VIDEO = "This video"
GET_ALL = "All {N}"
GET_ALL_PLAIN = "All"
GET_FIRST = "First…"
STEPPER_NAME = "How many videos"
SKIP_LONG = "Skip long files"
SKIP_LONG_CAPTION = "Over 7 min · {k} in this playlist"
IGNORE_DUPES = "Ignore duplicates"
IGNORE_DUPES_CAPTION = "Already in your library · {k} found"
PLAYLIST_REASON_UNREAD = "Playlist choices open once a playlist link is read"
PLAYLIST_REASON_SINGLE = "This link is one video, so there is no playlist to choose"

# -- Save to card ---------------------------------------------------------------
CARD_SAVE = "Save to"
CHANGE = "Change…"
FOLDER_NAME = "Destination folder"
PLAYLIST_FOLDER_NOTE = "A folder named after the playlist is made inside it"

# -- More options ---------------------------------------------------------------
MORE_OPTIONS = "More options: split chapters"
SPLIT_CHAPTERS = "Split into chapters"
SPLIT_CAPTION = "One file per chapter, for long single videos"
SPLIT_FOUND = "This video has {n} parts: turn this on to save each as its own file"
SPLIT_NONE = "This video has no chapters or timestamped tracklist to split by"
FOUND_PARTS = " · {n} parts"
PART_NAME = "Part {i} of {n}"

# -- preview / tracks pane ------------------------------------------------------
PREVIEW = "Preview"
TRACKS = "Tracks"
COL_TITLE = "Name"
COL_SIZE = "Size"
COL_STATUS = "Status"
COL_LENGTH = "Length"
PREVIEW_COUNTS = "{N} videos · {M} to download · {S} skipped"
PREVIEW_COUNTS_NO_SKIP = "{N} videos · {M} to download"
PREVIEW_COUNTS_ONE = "1 video · 1 to download"
TRACKS_COUNTS_ACTIVE = "{done} done · {dl} downloading · {wait} waiting · {skip} skipped"
TRACKS_COUNTS_FINAL = "{done} done · {skip} skipped"
TRACKS_COUNTS_FINAL_MISSING = "{done} done · {skip} skipped · {missing} not downloaded"
EMPTY_PREVIEW_TITLE = "Nothing to preview yet"
EMPTY_PREVIEW_BODY = "Paste a video or playlist link and it appears here before anything is downloaded."
SHOW_LIST = "Show list"
HIDE_LIST = "Hide list"

# -- track pills (status = icon + word) -----------------------------------------
PILL_HAVE = "You have it"
PILL_LONG = "Over 7 min"
PILL_DONE = "Done"
PILL_DOWNLOADING = "Downloading · {p}%"
PILL_CONVERTING = "Converting · {p}%"
CONVERTING_FILE = "Converting to MP3 · {name}"
CONVERTING_CAPTION = "Making the MP3 from the download; the original is removed when it is done"
SAVED_AS = "Saved as {name}"
SAVED_FILES = "Saved {n} files in {folder}"
SHOW_FILE = "Show file"
SIZE_ESTIMATE = "≈ {size}"
PILL_WAITING = "Waiting"
PILL_SKIP_HAVE = "You have it"
PILL_SKIP_LONG = "Over 7 min"
PILL_NOT_DOWNLOADED = "Not downloaded"

# -- progress ring --------------------------------------------------------------
RING_COUNT = "{done} of {total} files"
RING_A11Y_PROGRESS = "Overall progress {p} percent, {done} of {total} files"
RING_A11Y_DONE = "All {total} files downloaded"
CURRENT_FILE_NAME = "Current file"

# -- downloading view -----------------------------------------------------------
QUEUE_TITLE = "Queue another link"
QUEUE_NOTE = "Runs after this one"
QUEUE_ENTRY_NAME = "Link to queue"
ADD_TO_QUEUE = "Add to queue"
QUEUE_EMPTY = "Paste a link first, then add it to the queue"
QUEUE_WAITING = "{n} waiting · see Activity"
THIS_DOWNLOAD = "This download"
KEY_FORMAT = "Format"
KEY_SAVES_TO = "Saves to"
KEY_SKIPPING = "Skipping"
FORMAT_VALUE_AUDIO = "Audio · MP3 · 192 kbps"
FORMAT_VALUE_VIDEO = "Video · MP4 · {q}p"
SKIPPING_BOTH = "{d} you have · {l} over 7 min"
SKIPPING_DUPES = "{d} you have"
SKIPPING_LONG = "{l} over 7 min"
SKIPPING_NONE = "Nothing skipped"
FILE_CAPTION = "{done} of {total} · {speed} · about {eta} left"
ETA_LEFT = "about {eta} left"

# -- done view ------------------------------------------------------------------
DONE_TRACKS = "Downloaded {n} {word}"
DONE_STATS = "{size} in {time}"
DONE_STATS_TIME = "in {time}"
PLAY_IN_LIBRARY = "Play in Library"
SEE_IN_ACTIVITY = "See in Activity"
ANOTHER_TITLE = "Download another"
ANOTHER_NOTE = "Your last choices stay set: {choices}"
CHOICE_SKIP_LONG = "skip long"
CHOICE_IGNORE_DUPES = "ignore duplicates"

# -- action bar -----------------------------------------------------------------
WORD_TRACK = "track"
WORD_TRACKS = "tracks"
AB_NO_LINK = "Paste a video or playlist link to start"
AB_READY = "{M} {word} · {format}"
AB_READY_SIZE = "{M} {word} · {format} · about {size}"
AB_READY_CAPTION = "Saves to {folder}"
AB_READY_CAPTION_DUPES = "Saves to {folder} · skips {d} you have"
AB_READY_CAPTION_LONG = "Saves to {folder} · skips {l} over 7 min"
AB_READY_CAPTION_BOTH = "Saves to {folder} · skips {d} you have and {l} over 7 min"
AB_BUSY = "Downloading {i} of {M} · about {eta} left"
AB_BUSY_NO_ETA = "Downloading {i} of {M}"
FORMAT_SUMMARY_AUDIO = "Audio MP3"
FORMAT_SUMMARY_VIDEO = "Video MP4"
DOWNLOAD = "Download"
DOWNLOAD_HINT = "Ctrl+Enter"
CANCEL = "Cancel download"
CANCEL_HINT = "Esc"
AB_DONE = "Downloaded {n} {word} to {folder} · {time}"
AB_DONE_NO_TIME = "Downloaded {n} {word} to {folder}"
AB_ERROR_HEAD = "Nothing to download yet"
AB_ERROR_CAPTION = "Download opens once the link can be read"
AB_DONE_CAPTION = "Skipped {d} you already have and {l} over 7 min"
AB_DONE_CAPTION_DUPES = "Skipped {d} you already have"
AB_DONE_CAPTION_LONG = "Skipped {l} over 7 min"
AB_DONE_CAPTION_MISSING = "{k} did not finish"
OPEN_FOLDER = "Open folder"
BADGE_WAITING = "{n} waiting"

# -- Activity page ----------------------------------------------------------------
ACT_SEARCH_NAME = "Search activity"
ACT_SEARCH_PLACEHOLDER = "Search titles and links"
ACT_SHOW_NAME = "Show"
ACT_ALL = "All"
ACT_AUDIO = "Audio"
ACT_VIDEO = "Video"
ACT_PROBLEMS = "Problems"
ACT_NOW = "Now"
ACT_NOW_EMPTY = "Nothing is downloading"
ACT_NOW_COUNTS = "{done} of {total} · about {eta} left"
ACT_NOW_COUNTS_NO_ETA = "{done} of {total}"
ACT_NOW_KIND_PLAYLIST = "Playlist"
ACT_NOW_KIND_SINGLE = "Single video"
ACT_CANCEL = "Cancel"
ACT_UP_NEXT = "Up next"
ACT_UP_NEXT_NOTE = "Runs one at a time, in order"
ACT_UP_NEXT_EMPTY = "Nothing waiting"
ACT_REMOVE_FROM_QUEUE = "Remove {title} from the queue"
ACT_HISTORY = "History"
ACT_HISTORY_NOTE = "Every link you paste is kept here, downloaded or not"
ACT_TODAY = "Today"
ACT_YESTERDAY = "Yesterday"
ACT_RESULT_DONE = "Done"
ACT_RESULT_PARTIAL = "Partial"
ACT_RESULT_CANCELLED = "Cancelled"
ACT_RESULT_FAILED = "Failed"
ACT_RESULT_NOT_DOWNLOADED = "Not downloaded"
ACT_SHOW_FOLDER = "Show folder"
ACT_USE_THIS_LINK = "Use this link"
ACT_MORE_FOR = "More for {title}"
ACT_COPY_LINK = "Copy link"
ACT_REMOVE_FROM_HISTORY = "Remove from history"
ACT_LINK_COPIED = "Link copied"
ACT_ENTRIES = "{n} entries · kept on this computer only"
ACT_ENTRY = "1 entry · kept on this computer only"
ACT_CLEAR_OLDER = "Clear entries older than…"
ACT_CLEAR_DAYS = "Older than {d} days"
ACT_CLEAR_TITLE = "Clear {n} entries older than {d} days?"
ACT_CLEAR_BODY = "They are removed from this list. Files already downloaded stay on disk."
ACT_CLEAR_KEEP = "Keep them"
ACT_CLEAR_GO = "Clear {n} entries"
ACT_EMPTY_TITLE = "Nothing downloaded yet"
ACT_EMPTY_BODY = "Every link you paste appears here."
ACT_GO_TO_DOWNLOAD = "Go to Download"
ACT_KIND_PLAYLIST = "Playlist"
ACT_KIND_SINGLE = "Single video"
ACT_KIND_LINK = "Link"
ACT_CAPTION = "{kind} · {detail}"
ACT_TRACKS_COUNT = "{n} of {m} tracks"
ACT_SPLIT_CHAPTERS = "split into {n} chapters"
ACT_CANCELLED_CAPTION = "stopped by you after {done} of {total} · the {done} are kept"
ACT_NOT_DOWNLOADED_CAPTION = "Pasted, never downloaded"
ACT_FAILED_CAPTION = "nothing saved"
ACT_NOTHING_SAVED = "Nothing was downloaded"

# -- Library page -----------------------------------------------------------------
LIB_PLAYLISTS = "Playlists"
LIB_ALL_FILES = "All files"
LIB_VIEW_NAME = "View"
LIB_SEARCH_NAME = "Search the library"
LIB_SEARCH_PLACEHOLDER = "Search {n} files"
LIB_FILES = "{n} files"
LIB_FILE = "1 file"
LIB_LOOK_ALIKE = "{n} look alike"
LIB_TRASH = "Trash: {n} files"
LIB_TRASH_EMPTY = "Trash: empty"
LIB_RENAME = "Rename {name}"
LIB_RENAME_APPLY = "Apply"
LIB_RENAME_CANCEL = "Cancel"
LIB_BADGE_COLOUR = "Badge colour"
LIB_COLOUR_ACCENT = "Blue"
LIB_COLOUR_OK = "Green"
LIB_COLOUR_BUSY = "Light blue"
LIB_COLOUR_ATTENTION = "Amber"
LIB_COLOUR_ERROR = "Red"
LIB_COLOUR_MUTED = "Grey"
LIB_MORE_FOR = "More for {name}"
LIB_TIDY_NAMES = "Tidy names"
LIB_TIDY_ALL = "All {n} files · undo any time"
LIB_TIDY_CLEAN_UP = "Clean up"
LIB_TIDY_SHORTEN = "Shorten"
LIB_TIDY_CASE = "Case"
LIB_OP_CLEAN = "Clean up names"
LIB_OP_REMOVE_FILLER = "Remove filler words"
LIB_OP_REMOVE_SPECIAL = "Remove symbols"
LIB_OP_REPLACE_SPACES = "Spaces to underscores"
LIB_OP_TRUNCATE = "Cut to 35 characters"
LIB_OP_ABBREVIATE = "Shorten repeats"
LIB_OP_STANDARD = "Plain letters (ASCII)"
LIB_OP_NUMBER = "Add number prefix"
LIB_CASE_LOWER = "lower"
LIB_CASE_UPPER = "UPPER"
LIB_CASE_TITLE = "Title"
LIB_CASE_CAMEL = "Camel"
LIB_OP_REPLACEMENTS = "Apply replacements"
LIB_OP_DELETE_LONG = "Delete files over 7 min"
LIB_OP_DELETE_LONG_NOTE = "Moves long files to the playlist's trash"
LIB_PREVIEW = "Preview · {k} of {n} names change"
LIB_PREVIEW_NONE = "No names change"
LIB_PREVIEW_BECOMES = "becomes"
LIB_RENAME_K = "Rename {k} files"
LIB_MOVE_K = "Move {k} files to the trash"
LIB_CLOSE = "Close"
LIB_UNDO = "Undo"
LIB_UNDO_NONE = "Nothing to undo yet"
LIB_REDO = "Redo"
LIB_REDO_NONE = "Nothing to redo"
LIB_EMPTY_TITLE = "No downloads yet"
LIB_EMPTY_BODY = "Downloaded playlists and files appear here."
LIB_COL_NAME = "Name"
LIB_COL_LENGTH = "Length"
LIB_COL_SIZE = "Size"
LIB_COL_FOLDER = "Folder"
LIB_FILES_IN = "Files in {name}"
LIB_FILE_MORE = "More for {name}"
LIB_PLAY = "Play"
LIB_SHOW_IN_FOLDER = "Show in folder"
LIB_ADD_TO_FOLDER = "Add to folder…"
LIB_ADD_TO_FOLDER_TITLE = "Add {name} to a folder"
LIB_ADD_TO_FOLDER_BODY = "The file is copied, the original stays where it is."
LIB_MOVE_TO_TRASH = "Move to trash"
LIB_MOVE_TO_TRASH_NOTE = "Moves to the folder's trash"
LIB_ADD = "Add"
LIB_EMPTY_TRASH_TITLE = "Empty the trash for {name}?"
LIB_EMPTY_TRASH_BODY = "The {n} files below are deleted for good. Files still in the playlist are kept."
LIB_EMPTY_TRASH_KEEP = "Keep them"
LIB_EMPTY_TRASH_GO = "Delete {n} files"
LIB_STATS_TOTAL = "{n} files"
LIB_STATS_DUPES = "{n} with the same name"
LIB_STATS_SIZES = "{n} with the same size"
LIB_NO_FOLDER = "This playlist is not on disk any more"
LIB_SELECT_PROMPT = "Pick a playlist to see its files"

# -- player bar -------------------------------------------------------------------
PLB_PLAYER = "Player"
PLB_PREVIOUS = "Previous track"
PLB_PLAY = "Play (Space)"
PLB_PAUSE = "Pause (Space)"
PLB_NEXT = "Next track"
PLB_POSITION = "Position"
PLB_VOLUME = "Volume"
PLB_AUTO_NEXT = "Auto-next"
PLB_NOWHERE = "Nothing playing"
PLB_OF = "{playlist} · {i} of {n}"
PLB_VIDEO_EXTERNALLY = "Video plays in the system's player · there is no video pane in this app"
PLB_ERROR_TITLE = "Playback stopped"
PLB_ERROR_BODY = "The file could not be played. It may be missing or in a format this app cannot read."

# -- error view (what · why · next step) ----------------------------------------
TRY_AGAIN = "Try again"
DETAILS = "Details"
ERRORS = {
    "bot_check": {
        "title": "YouTube didn't let this computer in",
        "body": (
            "It asked to confirm you're not a bot. Signing in to YouTube in a web browser on this "
            "computer usually fixes this; the app finds and uses that sign-in by itself. If you use "
            "a VPN, another server may help; waiting 10 to 15 minutes sometimes does."
        ),
    },
    "rate_limited": {
        "title": "YouTube is limiting this computer",
        "body": (
            "It refused requests because too many came from here. Wait 10 to 15 minutes, " "then try again."
        ),
    },
    "unavailable": {
        "title": "This video can't be downloaded",
        "body": (
            "It is private, removed, members-only or blocked where you are. "
            "Check the link in your browser."
        ),
    },
    "unsupported": {
        "title": "This link isn't one the app can read",
        "body": (
            "It doesn't point to a video or playlist on a supported site. "
            "Copy the link from the video's page and paste it again."
        ),
    },
    "network": {
        "title": "The site couldn't be reached",
        "body": (
            "This computer seems to be offline, or the site didn't answer. "
            "Check your connection, then try again."
        ),
    },
    "unknown": {
        "title": "The link couldn't be read",
        "body": "The reason is under Details. Try again; if it keeps failing, a newer yt-dlp may help.",
    },
}

# -- Settings page ----------------------------------------------------------------
SET_CAPTION = "Changes save as you make them"
SET_CARD_DOWNLOADS = "Downloads"
SET_SAVE_TO = "Save to"
SET_CHANGE = "Change…"
SET_USE_DEFAULT = "Use default"
SET_FOLDER_NOTE = "Files and playlist folders go here. Default: {path}"
SET_FOLDER_DENIED = "That folder could not be created or written. The previous one is kept."
SET_FOLDER_NAME = "Download folder"
SET_FORMAT = "Format"
SET_FORMAT_NAME = "Default format"
SET_QUALITY = "Video quality"
SET_QUALITY_NAME = "Default video quality"
SET_LONG_MEANS = '"Long" means'
SET_LONG_NAME = "How many minutes long means"
SET_LONG_UNIT = " min"
SET_LONG_NOTE = "used by Skip long files"

SET_CARD_TIDY = "Tidy names"
SET_RESET_DEFAULTS = "Reset to defaults"
SET_RESET_TITLE = "Reset tidy names to the defaults?"
SET_RESET_BODY = "Your added words and replacements are replaced by the built-in ones."
SET_RESET_KEEP = "Keep mine"
SET_RESET_GO = "Reset to defaults"
SET_FILLER_NOTE = 'Filler words, removed by "Remove filler words"'
SET_REMOVE_WORD = "Remove {word}"
SET_MORE_WORDS = "+ {n} more"
SET_FEWER_WORDS = "Show the first 12"
SET_ADD_WORD = "Add a word"
SET_ADD = "Add"
SET_WORD_ADDED = "Added"
SET_WORD_EXISTS = "Already in the list"
SET_REPLACEMENTS = "Character replacements"
SET_FROM = "From"
SET_BECOMES = "becomes"
SET_TO = "To"
SET_REMOVE_REPLACEMENT = "Remove this replacement"
SET_ADD_REPLACEMENT = "Add replacement"
SET_REPLACEMENT_NEEDS_FROM = "Fill in the text to replace first"

SET_CARD_TOOLS = "Tools"
SET_READY = "Ready"
SET_NEEDS_YOU = "Needs you · missing"
SET_YTDLP = "yt-dlp"
SET_FFMPEG = "ffmpeg"
SET_CHECK_UPDATE = "Check for update"
SET_UPDATING = "Updating yt-dlp…"
SET_UPDATED = "Updated: {before} to {after}"
SET_ALREADY_NEW = "Already up to date: {version}"
SET_UPDATE_FAILED = "The update did not finish"
SET_UPDATE_BLOCKED = "yt-dlp comes from a system package here, so the app leaves updating to it"
SET_RESTART_NOTE = "The new version is used after the app restarts"
SET_DETAILS = "Details"
SET_FROM_SYSTEM = "from your system packages"

SET_CARD_SIGNIN = "YouTube sign-in"
SET_SIGNIN_NAME = "Browser sign-in"
SET_SIGNIN_AUTO = "Automatic (recommended)"
SET_SIGNIN_OFF = "Off"
SET_SIGNIN_SAVED = "Saved choice · {name} (checking…)"
SET_SIGNIN_NOW = "In use now: {words}"
SET_SIGNIN_NONE = "No signed-in browser found on this computer"
SET_SIGNIN_OFF_NOW = "Sign-in is off: YouTube may ask to confirm you're not a bot"
SET_SIGNIN_NOTE = (
    "The app reads only whether you are signed in. yt-dlp uses that browser's YouTube "
    "cookies on this computer and sends them only to YouTube."
)
SET_SIGNIN_CHECKING = "Looking for signed-in browsers…"

SET_CARD_PRIVACY = "Privacy"
SET_KEPT_HERE = "Kept here"
SET_KEPT_HERE_VALUE = "History, settings, the duplicate list and logs"
SET_FOLDER_KEY = "Folder"
SET_NETWORK = "Network"
SET_NETWORK_VALUE = "Only the sites you paste, through yt-dlp. No accounts, no telemetry, no AI."
SET_OPEN_DATA = "Open data folder"
SET_SAVE_DIAGNOSTICS = "Save diagnostics…"
SET_DIAG_SAVING = "Saving diagnostics…"
SET_DIAG_SAVED = "Saved to {path}"
SET_SHOW_FILE = "Show file"
SET_DIAG_FAILED = "The diagnostics file could not be written"

SET_CARD_ABOUT = "About"
SET_VERSION = "Version"
SET_VERSION_VALUE = "LinMediaDownloader 2.0.0 · GTK {gtk}"
SET_LICENCE = "Licence"
SET_LICENCE_VALUE = "CC BY-NC 4.0 · personal, non-commercial use"
SET_SHORTCUTS = "Keyboard shortcuts"
SET_SHORTCUTS_TITLE = "Keyboard shortcuts"
SET_HELP = "Help and FAQ"
SET_CREDITS = "Credits"
SET_CREDITS_TITLE = "Credits"
SET_CREDITS_WORDS = (
    "yt-dlp downloads and reads links. ffmpeg converts and splits. GTK and PyGObject draw "
    "the window. Icons: Phosphor (MIT). Font: Ubuntu. Styling and widgets: lintheme."
)

# -- help window (the 1.x FAQ, kept where it still applies to 2.0) -----------------
HELP_TITLE = "Help and FAQ"
HELP_SECTIONS = (
    (
        "What is LinMediaDownloader?",
        "A desktop app for saving YouTube media, as audio or video, single tracks or whole "
        "playlists, for personal use. yt-dlp downloads, ffmpeg converts and splits.",
    ),
    (
        "The download choices",
        "Paste a link and the app reads it: a live preview shows every track and which ones "
        "would be skipped. Audio is MP3 at 192 kbps; video is MP4 at up to 1080p. For a "
        "playlist you can take this video, all of it, or the first few.",
    ),
    (
        'How does "Split into chapters" work?',
        "Some long videos are many tracks in one. With this option the app downloads the "
        "single video, reads the chapter boundaries from its description, and splits it "
        "into one file per chapter. The whole file is kept only when no chapters are found.",
    ),
    (
        "Tidy names",
        "The Tidy names tool in the Library renames many files at once: removing filler "
        "words, symbols or spaces, shortening names, changing case. Every operation shows "
        "a preview first and can be undone.",
    ),
    (
        "Troubleshooting",
        'If YouTube answers "Sign in to confirm you\'re not a bot", sign in to YouTube in '
        "any browser on this computer and let the app use that sign-in (Settings). "
        "Converting and splitting need ffmpeg from your system packages.",
    ),
)

# -- shortcuts window ---------------------------------------------------------------
SHORTCUT_ROWS = (
    ("Ctrl+Enter", "Start the download"),
    ("Esc", "Cancel the running download"),
    ("Ctrl+L", "Focus the link field"),
    ("Ctrl+V", "Paste a link"),
    ("Alt+1 to 4", "Switch pages"),
    ("Space", "Play or pause"),
    ("Right / Left", "Seek 5 s forward, 2 s back"),
    ("Up / Down", "Volume"),
    ("Delete", "Stop and move the file to the trash"),
)
