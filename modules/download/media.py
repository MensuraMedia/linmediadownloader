#!/usr/bin/env python3
# modules/download/media.py
# Download functionality for YT Media Backup

import os
import threading
import itertools
import logging
from datetime import datetime
import yt_dlp
from modules.utils.file_utils import sanitize_filename
from modules.download import access
from modules.config.logging_config import YTDLPLogger
from modules.config.settings import (
    current_download,
    download_history,
    download_queue,
    reset_cancel,
    is_cancel_requested,
    long_seconds,
)

logger = logging.getLogger('lmd.media')

def get_video_info(url):
    """Get information about the video or playlist"""
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'skip_download': True,
        'logger': YTDLPLogger(logging.getLogger('lmd.ytdlp.info')),
        **access.ydl_options(),  # the user's browser sign-in + a local JS runtime
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Check if it's a playlist
            if '_type' in info and info['_type'] == 'playlist':
                # Get info for the first video to determine if this is a video within a playlist
                if len(info.get('entries', [])) > 0 and 'url' in info['entries'][0]:
                    first_video_url = info['entries'][0]['url']
                    try:
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl2:
                            video_info = ydl2.extract_info(first_video_url, download=False)
                            
                            return {
                                'is_playlist': True,
                                'is_video_in_playlist': True,
                                'title': info.get('title', 'Playlist'),
                                'video_title': video_info.get('title', 'Video'),
                                'entries': len(info.get('entries', [])),
                                'url': url,
                                'video_url': first_video_url
                            }
                    except Exception:
                        # If fetching individual video info fails, continue with playlist info
                        pass
                
                return {
                    'is_playlist': True,
                    'is_video_in_playlist': False,
                    'title': info.get('title', 'Playlist'),
                    'entries': len(info.get('entries', [])),
                    'url': url
                }
            else:
                # Check if this URL is part of a playlist by looking for the playlist parameter
                if 'list=' in url and 'youtube.com' in url:
                    # Try to get playlist info
                    playlist_url = url
                    if '&list=' in url:
                        playlist_url = 'https://www.youtube.com/playlist?list=' + url.split('&list=')[1].split('&')[0]
                    elif '?list=' in url:
                        playlist_url = 'https://www.youtube.com/playlist?list=' + url.split('?list=')[1].split('&')[0]
                    
                    try:
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl2:
                            playlist_info = ydl2.extract_info(playlist_url, download=False)
                            
                            if '_type' in playlist_info and playlist_info['_type'] == 'playlist':
                                return {
                                    'is_playlist': True,
                                    'is_video_in_playlist': True,
                                    'title': playlist_info.get('title', 'Playlist'),
                                    'video_title': info.get('title', 'Video'),
                                    'entries': len(playlist_info.get('entries', [])),
                                    'url': url,
                                    'playlist_url': playlist_url
                                }
                    except Exception:
                        # If fetching playlist info fails, continue with single video info
                        pass
                
                # Not a playlist
                return {
                    'is_playlist': False,
                    'title': info.get('title', 'Video'),
                    'url': url
                }
    except Exception as e:
        return {
            'is_playlist': False,
            'title': 'Unknown',
            'error': str(e),
            'url': url
        }

def track_key(info_dict):
    """The key a track is known by in current_download['tracks'] (video id, else title)"""
    info_dict = info_dict or {}
    return info_dict.get('id') or info_dict.get('title') or ''


def set_track(info_dict, state, progress=None, size=None, path=None):
    """Record one track's state: downloading, processing, done, skipped_long or skipped_duplicate.

    Lets a front end show each track's status in words instead of guessing it from
    which file name is current. Formats merged into one file report 'done' per part;
    the last report wins, which is the one that matters."""
    key = track_key(info_dict)
    if not key:
        return
    tracks = current_download.setdefault('tracks', {})
    entry = tracks.setdefault(key, {'title': (info_dict or {}).get('title', '')})
    entry['state'] = state
    if progress is not None:
        entry['progress'] = progress
    if size is not None:
        entry['size'] = size  # bytes of the finished file
    if path is not None:
        entry['path'] = path  # where the finished file was saved (after renaming)


AUDIO_BITRATE = 192  # kbit/s: FFmpegExtractAudio's preferredquality below
AUDIO_BYTES_PER_SECOND = AUDIO_BITRATE * 1000 / 8


def conversion_progress():
    """0-100 for the file being converted to MP3, from its size so far, or None.

    ffmpeg reports no progress through yt-dlp, and a long recording can take a
    minute to convert after a few seconds of downloading; the growing .mp3 against
    length x bitrate is a close, honest measure (the encoder is constant-bitrate).
    """
    conv = current_download.get('converting')
    if not conv or not conv.get('expected'):
        return None
    try:
        size = os.path.getsize(conv['target'])
    except OSError:
        return 0.0
    return min(99.0, size * 100.0 / conv['expected'])


def record_error(message):
    """Keep yt-dlp's error lines (the last 20) so a front end can say why tracks failed"""
    errors = current_download.setdefault('errors', [])
    errors.append(str(message))
    del errors[:-20]


class DownloadProgress:
    """Progress callback for YT-DLP"""
    def __init__(self, total_files=1, split_pending=False):
        self.current_file = ""
        self.total_files = total_files
        self.completed_files = 0
        self.skipped = 0  # entries the filters skipped (too long, duplicates): handled, not failed
        self.info = None   # richest info_dict seen (chapters/description) for splitting
        self.split_pending = split_pending  # defer 'completed' until the split runs
        self.done = False   # all expected files downloaded (independent of status)

    def progress_hook(self, d):
        """Handle download progress updates"""
        if d["status"] == "downloading":
            # Update current file info
            if "filename" in d and d["filename"] != self.current_file:
                self.current_file = d["filename"]
                filename = os.path.basename(d["filename"])
                current_download["current_file"] = filename
                current_download["message"] = f"Downloading: {filename}"
                # Track duration (seconds) for the Length column, when available
                info_dict = d.get("info_dict") or {}
                current_download["duration"] = info_dict.get("duration")
            
            # Calculate download progress with graceful fallbacks:
            #   1. exact/estimated byte totals (most common)
            #   2. fragment counts (DASH/HLS streams that report no byte total)
            downloaded_bytes = d.get("downloaded_bytes", 0)
            total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            frag_index = d.get("fragment_index") or 0
            frag_count = d.get("fragment_count") or 0
            speed = d.get("speed", 0)
            eta = d.get("eta", 0)

            if total_bytes:
                progress = downloaded_bytes / total_bytes * 100
            elif frag_count:
                progress = frag_index / frag_count * 100
            else:
                progress = 0

            set_track(d.get("info_dict"), 'downloading', progress)

            # Always provide consistent progress data
            current_download.update({
                'status': 'downloading',
                'downloaded_bytes': downloaded_bytes,
                'total_bytes': total_bytes,
                'fragment_index': frag_index,
                'fragment_count': frag_count,
                'speed': speed,
                'eta': eta,
                'progress': progress
            })
            
            if is_cancel_requested():
                current_download["status"] = "cancelled"
                current_download["message"] = "Download cancelled by user"
                raise yt_dlp.utils.DownloadCancelled("Download cancelled by user")
        
        elif d['status'] == 'finished':
            # One download finished: a .webm, or one half of a video+audio pair. The track
            # is not done yet: conversion, merging and the deletion of the source still run.
            # postprocessor_hook() marks it done once all of that is over.
            info_dict = d.get("info_dict") or {}
            set_track(info_dict, 'processing', 100)
            self.info = info_dict or self.info
            current_download.update({
                'status': 'processing',
                'progress': 100,
                'duration': info_dict.get("duration"),
                'message': f"Processing {os.path.basename(d['filename'])}..."
            })

        elif d['status'] == 'error':
            current_download.update({
                'status': 'error',
                'message': f"Error: {d.get('error', 'Unknown error')}"
            })

    def mark_skipped(self):
        """A filter skipped an entry. If it was the last one, the download is complete:
        skipped tracks are handled, not failed (1.x counted only saved files, so any
        playlist with a skip looked unfinished and was downloaded again by the
        "alternative method")."""
        self.skipped += 1
        if not self.done and self.completed_files and self.completed_files + self.skipped >= self.total_files:
            self.done = True
            if not self.split_pending:
                current_download.update({
                    'status': 'completed',
                    'total_progress': 100,
                    'message': 'Download completed successfully!',
                })

    def postprocessor_hook(self, d):
        """A file is complete only after its last post-processing step.

        yt-dlp runs MoveFiles (MoveFilesAfterDownloadPP) last for every file, after conversion (the
        .webm becomes an .mp3 and is deleted) or merging. Counting here instead of on
        the download's 'finished' also stops a video+audio pair counting twice.
        """
        info_dict = d.get('info_dict') or {}
        if d.get('status') == 'started' and d.get('postprocessor') == 'ExtractAudio':
            source = info_dict.get('filepath') or ''
            duration = info_dict.get('duration') or 0
            target = os.path.splitext(source)[0] + '.mp3'
            if (current_download.get('converting') or {}).get('target') == target:
                return  # yt-dlp reports the same start more than once
            current_download['converting'] = {
                'key': track_key(info_dict),
                'target': target,
                'expected': duration * AUDIO_BYTES_PER_SECOND,
            }
            set_track(info_dict, 'processing', 0)
            current_download['message'] = f"Converting {os.path.basename(source)} to MP3"
            logger.info('Converting to MP3: %s (%s s)', source, duration)
            return
        if d.get('status') != 'finished' or d.get('postprocessor') != 'MoveFiles':
            return
        current_download.pop('converting', None)
        path = info_dict.get('filepath') or ''
        size = os.path.getsize(path) if path and os.path.isfile(path) else None
        set_track(info_dict, 'done', 100, size=size, path=path)
        logger.info('Saved %s (%s bytes)', path, size)
        self.completed_files += 1
        self.info = info_dict or self.info
        try:  # record it (original title + id) so later runs can skip duplicates
            from modules.download import dedupe
            dedupe.record_download(info_dict)
        except Exception:
            pass
        current_download.update({
            'completed_files': self.completed_files,
            'message': f"Saved {os.path.basename(path)}" if path else 'Saved',
        })
        if self.total_files > 1:
            current_download['total_progress'] = min((self.completed_files * 100) / self.total_files, 100)
        if self.completed_files + self.skipped >= self.total_files:
            self.done = True
            if self.split_pending:
                # The split phase runs next and reports its own progress.
                current_download.update({
                    'status': 'processing',
                    'total_progress': 100,
                    'message': 'Downloaded — preparing to split into tracks…'
                })
            else:
                current_download.update({
                    'status': 'completed',
                    'total_progress': 100,
                    'message': 'Download completed successfully!'
                })


def download_media(url, output_dir, download_type='audio', playlist_mode='single',
                   skip_long=False, limit=0, split_chapters=False, ignore_dupes=False,
                   video_quality='1080'):
    """Download media from YouTube.

    video_quality caps the video resolution ('480', '720' or '1080'); it is ignored for
    audio downloads, which always fetch the best available audio.
    """
    reset_cancel()

    # "Split Multi-Chapter video" is a single-video operation: split ONE long video
    # into its chapters. Force single-video download so a playlist/radio URL
    # (e.g. list=RD...) resolves to the primary video, then gets split.
    if split_chapters:
        playlist_mode = 'single'

    current_download['status'] = 'starting'
    # Keep progress property for compatibility but we don't update it anymore
    current_download['progress'] = 0
    current_download['total_progress'] = 0
    current_download['completed_files'] = 0
    current_download['message'] = 'Preparing download...'
    current_download['current_file'] = ''
    current_download['skipped_duplicates'] = 0
    current_download['tracks'] = {}   # per-track state for the 2.0 track list (see set_track)
    current_download['errors'] = []   # yt-dlp error lines, newest last (see record_error)
    current_download.pop('converting', None)
    logger.info('Download start: %s | type=%s mode=%s quality=%s limit=%s skip_long=%s '
                'ignore_dupes=%s split=%s | to %s | yt-dlp %s | access %s',
                url, download_type, playlist_mode, video_quality, limit, skip_long, ignore_dupes,
                split_chapters, output_dir, yt_dlp.version.__version__, access.current().describe())
    
    # Get video info to check if it's a playlist
    info = get_video_info(url)
    current_download['is_playlist'] = info['is_playlist']
    current_download['output_path'] = output_dir

    # Enrich the most recent links-history entry with the resolved title
    from modules.config.settings import update_last_link_history
    update_last_link_history(title=info.get('title'))
    
    if info['is_playlist']:
        current_download['playlist_title'] = info['title']
        current_download['total_files'] = info.get('entries', 1)
    else:
        current_download['playlist_title'] = ''
        current_download['total_files'] = 1

    # Limit a playlist download to the top N items if requested
    if info['is_playlist'] and playlist_mode == 'playlist' and limit and limit > 0:
        current_download['total_files'] = min(current_download['total_files'], limit)
    
    # If it's a playlist but user selected single video, modify URL
    if info['is_playlist'] and playlist_mode == 'single':
        # If we have a specific video URL, use it
        if 'video_url' in info:
            url = info['video_url']
        else:
            # Extract the first video from the playlist
            url = url.split('&list=')[0] if '&list=' in url else url
        
        current_download['is_playlist'] = False
        current_download['total_files'] = 1
    
    # Create a directory for playlist if needed
    if info['is_playlist'] and playlist_mode == 'playlist':
        playlist_name = sanitize_filename(info['title'])
        output_dir = os.path.join(output_dir, f"{playlist_name}_playlist")
        os.makedirs(output_dir, exist_ok=True)
    
    progress_tracker = DownloadProgress(current_download['total_files'], split_pending=split_chapters)
    
    # Create a sanitize filename post-processor
    class SanitizeFilenamePP(yt_dlp.postprocessor.PostProcessor):
        def run(self, info):
            if 'filepath' in info:
                path_dir, path_file = os.path.split(info['filepath'])
                sanitized_file = sanitize_filename(path_file)
                new_path = os.path.join(path_dir, sanitized_file)
                
                if info['filepath'] != new_path:
                    try:
                        os.rename(info['filepath'], new_path)
                        info['filepath'] = new_path

                        # Update the filename in the info dictionary
                        if 'filename' in info:
                            info['filename'] = new_path
                    except Exception as e:
                        logger.error('Error renaming file: %s', e)
            
            # yt-dlp expects (files to delete, info); 1.x returned them swapped, so every
            # download ended with "unhashable type: 'dict'" after the file was saved
            return [], info
    
    # Setup common yt-dlp options
    ydl_opts = {
        'restrictfilenames': False,  # Don't restrict filenames - we'll sanitize them ourselves
        'progress_hooks': [progress_tracker.progress_hook],
        'postprocessor_hooks': [progress_tracker.postprocessor_hook],
        'ignoreerrors': True,
        'no_warnings': True,
        'geo_bypass': True,
        'extractor_retries': 5,
        'logger': YTDLPLogger(logging.getLogger('lmd.ytdlp.dl'), on_error=record_error),
        **access.ydl_options(),  # the user's browser sign-in + a local JS runtime
    }

    # Optional filters: skip long tracks (>7 min) and/or already-downloaded ones.
    if skip_long or ignore_dupes:
        from modules.download import dedupe

        def _combined_filter(info_dict, *, incomplete=False):
            if skip_long:
                dur = info_dict.get('duration')
                if dur is not None and dur > long_seconds():
                    set_track(info_dict, 'skipped_long')
                    progress_tracker.mark_skipped()
                    return f"Skipping long file (>7 min): {info_dict.get('title', '')}"
            if ignore_dupes and dedupe.is_duplicate(info_dict):
                current_download['skipped_duplicates'] = \
                    current_download.get('skipped_duplicates', 0) + 1
                set_track(info_dict, 'skipped_duplicate')
                progress_tracker.mark_skipped()
                return f"Skipping duplicate: {info_dict.get('title', '')}"
            return None
        ydl_opts['match_filter'] = _combined_filter

    # Limit a playlist to the top N items (yt-dlp downloads items 1..N)
    if info['is_playlist'] and playlist_mode == 'playlist' and limit and limit > 0:
        ydl_opts['playlistend'] = limit


    if download_type == 'audio':
        # For audio, set specific options to only download and process audio
        audio_output_template = os.path.join(output_dir, '%(title)s.%(ext)s')
        ydl_opts.update({
            'outtmpl': audio_output_template,
            'format': 'bestaudio',  # Only select audio streams
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'keepvideo': False,  # Important: Don't keep the video file after extraction
        })
    else:  # video
        # For video, download video capped at the requested resolution (720p or
        # 1080p). The height<= filters keep every fallback within the cap; the
        # final 'best' guards against a source with no stream at/under the cap.
        try:
            height = int(video_quality)
        except (TypeError, ValueError):
            height = 1080
        if height not in (480, 720, 1080):
            height = 1080
        video_output_template = os.path.join(output_dir, '%(title)s.%(ext)s')
        ydl_opts.update({
            'outtmpl': video_output_template,
            'format': (
                f'bestvideo[ext=mp4][height<={height}]+bestaudio[ext=m4a]/'
                f'best[ext=mp4][height<={height}]/'
                f'best[height<={height}]/best'
            ),
            'merge_output_format': 'mp4',
        })
    
    # IMPORTANT FIX: For playlists, we need to ensure we're using the correct URL format
    if info['is_playlist'] and playlist_mode == 'playlist':
        # Remove noplaylist option which may cause issues
        if 'noplaylist' in ydl_opts:
            del ydl_opts['noplaylist']
        
        # Add the yes-playlist option to ensure all videos are downloaded
        ydl_opts['noplaylist'] = False
        
        # If we have a playlist URL but it's not in the correct format, fix it
        if 'playlist_url' in info:
            url = info['playlist_url']
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Add sanitize filename post-processor
            ydl.add_post_processor(SanitizeFilenamePP())
            
            # Start the download
            ydl.download([url])
        
        # Final pass to sanitize all filenames in the output directory
        for filename in os.listdir(output_dir):
            filepath = os.path.join(output_dir, filename)
            if os.path.isfile(filepath):
                sanitized = sanitize_filename(filename)
                if filename != sanitized:
                    try:
                        sanitized_path = os.path.join(output_dir, sanitized)
                        if not os.path.exists(sanitized_path):  # Avoid overwriting existing files
                            os.rename(filepath, sanitized_path)
                    except Exception as e:
                        logger.error('Error renaming %s: %s', filename, e)
        
        # If the download didn't actually finish, try alternative method
        if not progress_tracker.done:
            # If we're missing files or there was an error code, try alternative method
            current_download['message'] = 'Trying alternative download method...'
            
            # Modify options for alternative method
            if download_type == 'audio':
                ydl_opts.update({
                    'extractor_args': {'youtube': {'player_client': ['android']}},
                })
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Add sanitize filename post-processor
                ydl.add_post_processor(SanitizeFilenamePP())
                
                # Try the download again
                ydl.download([url])
            
            # If the retry still didn't finish, handle any errors
            if not progress_tracker.done:
                # Check if we had partial success (some files downloaded)
                actual_count = current_download['completed_files']
                expected_count = current_download['total_files']
                
                if actual_count < expected_count and info['is_playlist']:
                    current_download['status'] = 'completed_with_errors'
                    current_download['message'] = f'Download incomplete. Only {actual_count} of {expected_count} files were downloaded.'
                else:
                    current_download['status'] = 'completed_with_errors'
                    current_download['message'] = 'Download completed with some errors or skipped files.'
            
            # Final filename sanitization for alternative method
            for filename in os.listdir(output_dir):
                filepath = os.path.join(output_dir, filename)
                if os.path.isfile(filepath):
                    sanitized = sanitize_filename(filename)
                    if filename != sanitized:
                        try:
                            sanitized_path = os.path.join(output_dir, sanitized)
                            if not os.path.exists(sanitized_path):  # Avoid overwriting existing files
                                os.rename(filepath, sanitized_path)
                        except Exception as e:
                            logger.error('Error renaming %s: %s', filename, e)
        
        # Add to download history (timestamped for reliable descending sort).
        # Record the real download outcome, not the deferred 'processing' state.
        hist_status = 'completed' if progress_tracker.done else current_download['status']
        download_history.append({
            'url': url,
            'output_dir': output_dir,
            'download_type': download_type,
            'is_playlist': info['is_playlist'],
            'title': info.get('title', 'Unknown'),
            'status': hist_status,
            'timestamp': datetime.now().isoformat(timespec='seconds')
        })
        # Save history to persistent storage
        from modules.config.settings import save_download_history
        save_download_history()

        # Optional: split the single downloaded video into per-track files.
        # This runs while status is 'processing' and reports its own progress,
        # then sets the final 'completed' state — so the UI never says "done" early.
        if split_chapters:
            try:
                _split_into_tracks(output_dir, progress_tracker.info, info.get('title'))
            except Exception as e:
                logger.error('Chapter split error: %s', e)
                current_download['status'] = 'completed'
                current_download['message'] = f'Downloaded (split failed: {e})'

    except yt_dlp.utils.DownloadCancelled:
        # User cancelled mid-download: report it as cancelled, not an error,
        # and skip the alternative-method retry.
        current_download['status'] = 'cancelled'
        current_download['message'] = 'Download cancelled by user'
    except Exception as e:
        current_download['status'] = 'error'
        current_download['message'] = f'Error: {str(e)}'

    # A playlist folder made for this download stays only if something was saved in it.
    _remove_if_empty(output_dir)
    saved = [t.get('path') for t in (current_download.get('tracks') or {}).values()
             if t.get('state') == 'done' and t.get('path') and os.path.exists(t['path'])]  # a split removes its source
    errors = current_download.get('errors') or []
    logger.info('Download end: %s | status=%s | %d file(s) saved | %d error(s)%s%s',
                url, current_download['status'], len(saved), len(errors),
                ''.join(f'\n    saved: {path}' for path in saved),
                ''.join(f'\n    error: {err[:300]}' for err in errors[-5:]))

    # Record the final outcome against the links-history entry (all exit paths).
    update_last_link_history(status=current_download['status'])


def _remove_if_empty(folder):
    """Remove a "<name>_playlist" folder the download made and left empty"""
    if not folder or not folder.endswith('_playlist') or not os.path.isdir(folder):
        return
    try:
        if not os.listdir(folder):
            os.rmdir(folder)
            logger.info('Removed empty folder %s (nothing was saved in it)', folder)
    except OSError as e:
        logger.warning('Could not remove empty folder %s: %s', folder, e)


def _split_into_tracks(output_dir, meta, fallback_title):
    """Split the just-downloaded single file into per-track files via chapters/tracklist.

    Reports progress through current_download (status 'processing') so the UI shows
    live split progress, and only sets 'completed' when the split is done.
    """
    from modules.download.chapters import chapter_segments, split_file, MEDIA_EXTS
    meta = meta or {}
    segments = chapter_segments(meta, meta.get('duration'))
    title = meta.get('title') or fallback_title or 'video'

    if not segments:
        # No tracklist — the whole file is kept; download is complete.
        current_download['status'] = 'completed'
        current_download['message'] = 'Downloaded (no chapters/tracklist found to split)'
        return

    # Find the file we just downloaded (newest top-level media file)
    cands = [os.path.join(output_dir, f) for f in os.listdir(output_dir)
             if os.path.isfile(os.path.join(output_dir, f))
             and os.path.splitext(f)[1].lower() in MEDIA_EXTS]
    if not cands:
        current_download['status'] = 'completed'
        current_download['message'] = 'Downloaded (source file not found for split)'
        return
    src = max(cands, key=os.path.getmtime)
    tracks_dir = os.path.join(output_dir, (sanitize_filename(title) or 'tracks') + '_playlist')

    total = len(segments)
    # Reframe the progress UI for the split phase
    current_download.update({
        'status': 'processing',
        'is_playlist': True,
        'playlist_title': f'{title} — splitting into tracks',
        'total_files': total,
        'completed_files': 0,
        'total_progress': 0,
        'current_file': '',
        'message': f'Splitting into {total} tracks…',
    })

    def on_progress(i, count, seg_title):
        set_track({'id': f'part-{i + 1}', 'title': seg_title}, 'processing', 0)
        current_download.update({
            'status': 'processing',
            'current_file': seg_title,
            'completed_files': i,
            'total_progress': min(i * 100 / count, 100),
            'message': f'Splitting track {i + 1} of {count}…',
        })

    def on_done(i, path):
        set_track({'id': f'part-{i + 1}'}, 'done', 100, size=os.path.getsize(path), path=path)
        logger.info('Saved part %d of %d: %s', i + 1, total, path)

    res = split_file(src, segments, tracks_dir, title, on_progress=on_progress, on_done=on_done)
    made = res.get('tracks', 0)
    if made:
        try:
            os.remove(src)  # keep only the split tracks
        except OSError:
            pass
        # Point the History entry at the actual tracks folder (not the download root),
        # so its "open folder" link lands where the split files really are.
        try:
            if download_history:
                download_history[-1]['output_dir'] = tracks_dir
                from modules.config.settings import save_download_history
                save_download_history()
        except Exception:
            pass
    current_download.update({
        'status': 'completed',
        'completed_files': made,
        'total_files': total,
        'total_progress': 100,
        'message': f'Split into {made} tracks' if made else 'Split produced no tracks',
    })


def start_download_thread(url, output_dir, download_type='audio', playlist_mode='single',
                          skip_long=False, limit=0, split_chapters=False, ignore_dupes=False,
                          video_quality='1080'):
    """Run a single download in a background thread (used directly by tests)."""
    download_thread = threading.Thread(
        target=download_media,
        args=(url, output_dir, download_type, playlist_mode, skip_long, limit,
              split_chapters, ignore_dupes, video_quality)
    )
    download_thread.daemon = True
    download_thread.start()
    return download_thread


# ── Download queue ────────────────────────────────────────────────────────────
# Jobs run one at a time; adding a link while one runs queues it. The Pending
# page reads download_queue; finished jobs stay in the list (for history there).
_job_counter = itertools.count(1)
_queue_lock = threading.Lock()

_ACTIVE_STATUSES = ('starting', 'downloading', 'processing')


def _download_active():
    """True if a download is currently running (by live status or an active job)."""
    if current_download.get('status') in _ACTIVE_STATUSES:
        return True
    return any(j.get('status') == 'active' for j in download_queue)


def enqueue_download(url, output_dir, download_type='audio', playlist_mode='single',
                     skip_long=False, limit=0, split_chapters=False, ignore_dupes=False,
                     video_quality='1080'):
    """Add a job to the queue and start it if nothing is running. Returns the job."""
    job = {
        'id': next(_job_counter),
        'url': url,
        'output_dir': output_dir,
        'download_type': download_type,
        'playlist_mode': playlist_mode,
        'skip_long': skip_long,
        'limit': limit,
        'split_chapters': split_chapters,
        'ignore_dupes': ignore_dupes,
        'video_quality': video_quality,
        'title': url,
        'status': 'queued',
        'queued_at': datetime.now().isoformat(timespec='seconds'),
    }
    download_queue.append(job)
    _start_next_if_idle()
    return job


def _start_next_if_idle():
    """Start the next queued job if nothing is currently downloading."""
    with _queue_lock:
        if _download_active():
            return
        nxt = next((j for j in download_queue if j.get('status') == 'queued'), None)
        if not nxt:
            return
        nxt['status'] = 'active'
    t = threading.Thread(target=_run_job, args=(nxt,), daemon=True)
    t.start()


def _run_job(job):
    """Run one queued job to completion, then start the next."""
    try:
        current_download['job_id'] = job['id']
        download_media(job['url'], job['output_dir'], job['download_type'],
                       job['playlist_mode'], job['skip_long'], job['limit'],
                       job['split_chapters'], job['ignore_dupes'],
                       job.get('video_quality', '1080'))
        job['title'] = (current_download.get('playlist_title')
                        or current_download.get('current_file') or job['title'])
        job['status'] = current_download.get('status', 'completed')
    except Exception as e:
        job['status'] = 'error'
        job['title'] = f"{job['title']} (error: {e})"
    finally:
        _start_next_if_idle()
