#!/usr/bin/env python3
# browser_app.py
# Fallback version of the app for browser access

import logging
from flask import Flask

# Configure logging before importing the rest so startup is captured.
from modules.config.logging_config import setup_logging
setup_logging()
logger = logging.getLogger('lmd.browser')

# Import modules
from modules.routes.ui import ui_routes
from modules.routes.api import api_routes
from modules.config.settings import SECRET_KEY, default_download_path

# Initialize Flask app
app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = SECRET_KEY

# Register blueprints
app.register_blueprint(ui_routes)
app.register_blueprint(api_routes)

if __name__ == '__main__':
    # Create a custom folder selection functionality for browser mode
    class BrowserFolderSelector:
        def openFileDialog(self, isFolder=False):
            """Simple function that returns the downloads folder path"""
            return default_download_path

    # Add this to the Flask app's globals for templates
    app.jinja_env.globals.update(
        pywebview=dict(
            api=BrowserFolderSelector()
        )
    )
    
    # Show startup message
    logger.info('Linux Media Downloader running in browser mode')
    logger.info('Open your browser and navigate to: http://127.0.0.1:5000')
    logger.info('Press Ctrl+C to stop the server.')

    # Run Flask app
    app.run(debug=False, host='127.0.0.1', port=5000)
