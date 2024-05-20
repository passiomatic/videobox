from setuptools import setup
import videobox

APP = ['macos/app.py']
DATA_FILES = ['macos/menubar-icon.svg']
OPTIONS = {
    # List here specific app packages, in addition tp those in pyproject.toml
    'packages': ['rumps', 'videobox'],
    # Copy these files outside the app bundle lib/python39.zip archive
    'resources': ['./videobox/templates', './videobox/static'], 
    # Tweak app Info.plist file
    'plist': {
        'CFBundleIdentifier': 'com.passiomatic.videobox',
        'LSUIElement': True,
        'CFBundleShortVersionString': videobox.__version__,
        'NSHumanReadableCopyright': '© Andrea Peltrin'
    },
    'iconfile': 'build/icon.icns'
}

setup(
    name='Videobox',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
