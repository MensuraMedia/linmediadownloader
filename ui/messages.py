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
CHIP_TOOLS_OK = "yt-dlp and ffmpeg · Ready"
CHIP_TOOLS_NO_YTDLP = "Needs you · yt-dlp is missing"
CHIP_TOOLS_NO_FFMPEG = "Needs you · ffmpeg is missing"
CHIP_READING = "Busy · reading the link"
CHIP_DOWNLOADING = "Busy · downloading {i} of {M}"
CHIP_CANT_REACH = "Can't reach · {site}"
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

# -- preview / tracks pane ------------------------------------------------------
PREVIEW = "Preview"
TRACKS = "Tracks"
COL_NUM = "#"
COL_TITLE = "Title"
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
PILL_HAVE = "You have it · skip"
PILL_LONG = "Over 7 min · skip"
PILL_DONE = "Done"
PILL_DOWNLOADING = "Downloading · {p}%"
PILL_WAITING = "Waiting"
PILL_SKIP_HAVE = "Skipped · you have it"
PILL_SKIP_LONG = "Skipped · over 7 min"
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

# -- error view (what · why · next step) ----------------------------------------
TRY_AGAIN = "Try again"
DETAILS = "Details"
ERRORS = {
    "bot_check": {
        "title": "YouTube didn't let this computer in",
        "body": (
            "It asked to confirm you're not a bot. If you use a VPN, another server may help; "
            "signing in through your web browser usually fixes this (coming soon); waiting 10 to "
            "15 minutes sometimes does."
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
