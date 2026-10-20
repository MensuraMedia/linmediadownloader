# tests/conftest.py
# Point the app's data directory at a throwaway folder before any app module is
# imported, so tests never read or write the real ~/.local/share/linmediadownloader;
# and give the vendored lintheme tests the ROOT and display marker they expect.

import os
import sys
import tempfile

import pytest

os.environ['LMD_DATA_DIR'] = tempfile.mkdtemp(prefix='lmd-test-data-')
os.environ['LMD_NO_MIGRATE'] = '1'
os.environ['LMD_BROWSER_ACCESS'] = 'off'  # never read the user's real browser profiles

# The vendored lintheme tests (tests/test_kit_*.py) import these two names.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

requires_display = pytest.mark.skipif(
    not os.environ.get('DISPLAY') and not os.environ.get('WAYLAND_DISPLAY'),
    reason='no display: run with a desktop session or xvfb-run -a',
)


@pytest.fixture(autouse=True)
def _no_file_manager(monkeypatch):
    """Tests never open the user's file manager: a test that checks what would be shown
    patches these itself; any other call fails loudly instead of opening a window."""
    from modules.utils import file_utils

    def refuse(*args, **kwargs):
        raise AssertionError(f"a test tried to open the file manager: {args}")

    for name in ("open_folder", "show_file", "show_items"):
        monkeypatch.setattr(file_utils, name, refuse)
