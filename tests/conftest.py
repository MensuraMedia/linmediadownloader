# tests/conftest.py
# Point the app's data directory at a throwaway folder before any app module is
# imported, so tests never read or write the real ~/.local/share/linmediadownloader.

import os
import tempfile

os.environ['LMD_DATA_DIR'] = tempfile.mkdtemp(prefix='lmd-test-data-')
os.environ['LMD_NO_MIGRATE'] = '1'
