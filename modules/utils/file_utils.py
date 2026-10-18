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
    """Open the file manager at a file with the file selected.

    Uses the freedesktop FileManager1 D-Bus interface (Nemo, Nautilus, Dolphin…);
    falls back to opening the folder when no file manager answers.
    """
    file_path = os.path.abspath(file_path)
    try:
        from urllib.parse import quote
        uri = 'file://' + quote(file_path)
        subprocess.run(
            ['gdbus', 'call', '--session', '--dest', 'org.freedesktop.FileManager1',
             '--object-path', '/org/freedesktop/FileManager1',
             '--method', 'org.freedesktop.FileManager1.ShowItems', f"['{uri}']", ''],
            check=True, capture_output=True, timeout=5,
        )
        logger.info('Showed %s in the file manager', file_path)
        return {"status": "success"}
    except Exception as e:
        logger.info('FileManager1 could not show %s (%s); opening its folder', file_path, e)
        return open_folder(os.path.dirname(file_path))
