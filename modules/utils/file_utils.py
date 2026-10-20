#!/usr/bin/env python3
# modules/utils/file_utils.py
# File system utilities for YT Media Backup

import os
import re
import subprocess
import logging

logger = logging.getLogger('lmd.files')

def sanitize_filename(filename):
    """Sanitize filenames: 
    1. Keep only alphanumeric chars
    2. Replace spaces & dashes with underscores
    3. Remove leading/trailing underscores
    4. Replace multiple underscores with a single one
    """
    # First, strip leading/trailing whitespace
    filename = filename.strip()
    
    # Extract extension if present (to preserve it)
    extension = ""
    if '.' in filename:
        base, extension = os.path.splitext(filename)
    else:
        base = filename
        extension = ""
    
    # Remove special characters (keep only alphanumeric, spaces, dashes)
    sanitized = re.sub(r'[^\w\s-]', '', base)
    
    # Replace spaces and dashes with underscores
    sanitized = re.sub(r'[\s-]+', '_', sanitized)
    
    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')
    
    # Replace multiple underscores with a single underscore
    sanitized = re.sub(r'_+', '_', sanitized)
    
    # Add the extension back
    return sanitized + extension

def open_folder(folder_path):
    """Open a folder in the file explorer"""
    # Ensure the path is absolute
    if not os.path.isabs(folder_path):
        folder_path = os.path.abspath(folder_path)
    
    # Create folder if it doesn't exist
    if not os.path.exists(folder_path):
        try:
            os.makedirs(folder_path, exist_ok=True)
        except Exception as e:
            return {"status": "error", "message": f"Could not create folder: {str(e)}"}
    
    try:
        # Use xdg-open on Linux
        subprocess.Popen(['xdg-open', folder_path])
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": f"Error opening folder: {str(e)}"}


def show_file(file_path):
    """Open the file manager at a file with the file selected"""
    return show_items([file_path])


def show_items(paths):
    """Open the file manager at the items' folder with the items selected.

    Works for files and folders (a folder is shown selected inside its parent). Uses the
    freedesktop FileManager1 D-Bus interface (Nemo, Nautilus, Dolphin…); falls back to
    opening the first item's folder when no file manager answers.
    """
    from urllib.parse import quote
    paths = [os.path.abspath(path).rstrip(os.sep) or os.sep for path in paths if path]
    if not paths:
        return {"status": "error", "message": "Nothing to show"}
    try:
        uris = ", ".join("'file://" + quote(path) + "'" for path in paths)
        subprocess.run(
            ['gdbus', 'call', '--session', '--dest', 'org.freedesktop.FileManager1',
             '--object-path', '/org/freedesktop/FileManager1',
             '--method', 'org.freedesktop.FileManager1.ShowItems', f"[{uris}]", ''],
            check=True, capture_output=True, timeout=5,
        )
        logger.info('Showed %s in the file manager', paths)
        return {"status": "success"}
    except Exception as e:
        logger.info('FileManager1 could not show %s (%s); opening its folder', paths, e)
        return open_folder(os.path.dirname(paths[0]))
