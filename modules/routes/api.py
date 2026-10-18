#!/usr/bin/env python3
# modules/routes/api.py
# API routes for YT Media Backup

import os
import logging
from flask import Blueprint, request, jsonify, send_file

logger = logging.getLogger('lmd.api')
from modules.config.settings import default_download_path
from modules.download.media import get_video_info
from modules.download import jobs
from modules.utils.file_utils import open_folder

# Create blueprint
api_routes = Blueprint('api_routes', __name__)

@api_routes.route('/api/check-url', methods=['POST'])
def check_url():
    """Check if URL is a single video or playlist"""
    data = request.get_json()
    url = data.get('url', '')
    
    if not url:
        return jsonify({'error': 'No URL provided'})
    
    info = get_video_info(url)
    return jsonify(info)

@api_routes.route('/api/get-default-path')
def get_default_path():
    """Get the default download path"""
    return jsonify({"path": default_download_path})

@api_routes.route('/api/download', methods=['POST'])
def start_download():
    """Queue a download; it starts at once if nothing else is running."""
    data = request.get_json(silent=True) or {}
    url = data.get('url', '')
    if not url:
        return jsonify({'error': 'No URL provided'})
    return jsonify(jobs.submit_download(url, data))

@api_routes.route('/api/cancel-download', methods=['POST'])
def cancel_download():
    """Cancel the current download process"""
    jobs.cancel_active_download()
    return jsonify({"status": "cancelled"})


@api_routes.route('/api/download-status')
def download_status():
    """Get the current download status (+ how many jobs are still queued)."""
    return jsonify(jobs.status_snapshot())


@api_routes.route('/api/queue')
def queue_route():
    """Return the download queue (queued, active, and finished jobs) for Pending."""
    return jsonify(jobs.queue_snapshot())


@api_routes.route('/api/clear-queue-finished', methods=['POST'])
def clear_queue_finished_route():
    """Remove finished/errored/cancelled jobs from the queue list."""
    return jsonify({'status': 'ok', 'remaining': jobs.clear_finished_jobs()})

@api_routes.route('/api/links-history')
def links_history_route():
    """Return the links history, newest first."""
    from modules.config.settings import links_history
    return jsonify(list(reversed(links_history)))


@api_routes.route('/api/clear-links-history', methods=['POST'])
def clear_links_history():
    """Clear the entire links history."""
    from modules.config.settings import links_history, save_links_history
    links_history.clear()
    save_links_history()
    return jsonify({'status': 'cleared'})


@api_routes.route('/api/playlists')
def playlists_route():
    """List previously-downloaded playlists (folders with more than one track)."""
    from modules import playlists
    return jsonify(playlists.list_playlists())


@api_routes.route('/api/playlist-files', methods=['POST'])
def playlist_files_route():
    """List the media files in a playlist folder (length / name / size)."""
    from modules import playlists
    path = (request.get_json() or {}).get('path', '')
    files = playlists.list_playlist_files(path)
    if files is None:
        return jsonify({'error': 'Invalid or unknown playlist path'}), 400
    return jsonify({'path': path, 'files': files,
                    'trash_count': playlists.trash_count(path), **playlists.stack_state()})


@api_routes.route('/api/rename-playlist', methods=['POST'])
def rename_playlist_route():
    """Rename a playlist folder on disk."""
    from modules import playlists
    data = request.get_json() or {}
    return jsonify(playlists.rename_playlist(data.get('path', ''), data.get('new_name', '')))


@api_routes.route('/api/playlist-operation', methods=['POST'])
def playlist_operation_route():
    """Apply a bulk file operation to a playlist folder."""
    from modules import playlists
    data = request.get_json() or {}
    return jsonify(playlists.apply_operation(data.get('path', ''), data.get('operation', '')))


@api_routes.route('/api/playlist-undo', methods=['POST'])
def playlist_undo_route():
    """Undo the most recent playlist file operation."""
    from modules import playlists
    return jsonify(playlists.undo_last())


@api_routes.route('/api/playlist-redo', methods=['POST'])
def playlist_redo_route():
    """Redo the most recently undone playlist file operation."""
    from modules import playlists
    return jsonify(playlists.redo_last())


@api_routes.route('/api/playlist-color', methods=['POST'])
def playlist_color_route():
    """Set the badge color for a playlist."""
    from modules import playlists
    data = request.get_json() or {}
    return jsonify(playlists.set_playlist_color(data.get('path', ''), data.get('color', '')))


@api_routes.route('/api/playlist-empty-trash', methods=['POST'])
def playlist_empty_trash_route():
    """Permanently purge a playlist's .trash folder."""
    from modules import playlists
    path = (request.get_json() or {}).get('path', '')
    return jsonify(playlists.empty_trash(path))


@api_routes.route('/api/all-media')
def all_media_route():
    """List every downloaded media file (for the Player)."""
    from modules import playlists
    return jsonify(playlists.list_all_media())


@api_routes.route('/api/media')
def serve_media_route():
    """Stream a media file (supports range requests for seeking)."""
    from modules import playlists
    path = request.args.get('path', '')
    if not playlists.is_safe_path(path) or not os.path.isfile(path):
        return jsonify({'error': 'Not found'}), 404
    return send_file(path, conditional=True)


@api_routes.route('/api/app-media')
def app_media_route():
    """List media files this app recorded (for the File Manager)."""
    from modules import playlists
    return jsonify(playlists.list_app_media())


@api_routes.route('/api/file-stats')
def file_stats_route():
    """Stats over app-recorded files (total / duplicate names / same size)."""
    from modules import playlists
    return jsonify(playlists.file_stats())


@api_routes.route('/api/global-operation', methods=['POST'])
def global_operation_route():
    """Apply a text operation across every app folder as one undoable action."""
    from modules import playlists
    op = (request.get_json() or {}).get('operation', '')
    return jsonify(playlists.global_operation(op))


@api_routes.route('/api/delete-media', methods=['POST'])
def delete_media_route():
    """Move a single media file to trash."""
    from modules import playlists
    path = (request.get_json() or {}).get('path', '')
    return jsonify(playlists.delete_media_file(path))


@api_routes.route('/api/add-to-folder', methods=['POST'])
def add_to_folder_route():
    """Copy a media file into a (new) curation folder."""
    from modules import playlists
    data = request.get_json() or {}
    return jsonify(playlists.add_to_folder(data.get('path', ''), data.get('folder', '')))


@api_routes.route('/api/settings')
def get_settings_route():
    """Return the user-editable text-control settings."""
    from modules.config import user_settings
    return jsonify(user_settings.get_settings())


@api_routes.route('/api/settings', methods=['POST'])
def save_settings_route():
    """Save filler words + character replacements."""
    from modules.config import user_settings
    data = request.get_json() or {}
    return jsonify(user_settings.save_settings(data))


@api_routes.route('/api/settings/reset', methods=['POST'])
def reset_settings_route():
    """Reset text-control settings to defaults."""
    from modules.config import user_settings
    return jsonify(user_settings.save_settings(user_settings._defaults()))


@api_routes.route('/api/open-folder', methods=['POST'])
def api_open_folder():
    """Open a folder in the file explorer"""
    data = request.get_json()
    folder_path = data.get('path', '')
    
    result = open_folder(folder_path)
    return jsonify(result)
