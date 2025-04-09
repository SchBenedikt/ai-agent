"""
Script zum Erstellen einer macOS-App mit py2app
"""

from setuptools import setup
import sys
import os

# Prüfen, ob alias-Modus verwendet werden soll 
# (schnellerer Build für Entwicklung/Tests)
if '--alias' in sys.argv:
    sys.argv.remove('--alias')
    ALIAS = True
else:
    ALIAS = False

APP = ['app.py']
DATA_FILES = [('.', ['requirements.txt'])]

OPTIONS = {
    'argv_emulation': False,
    'plist': {
        'CFBundleName': 'Gemini Assistant',
        'CFBundleDisplayName': 'Gemini Assistant',
        'CFBundleIdentifier': 'com.mycompany.geminiassistant',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSMicrophoneUsageDescription': 'Mikrofon-Zugriff für Spracherkennung',
        'NSCameraUsageDescription': 'Kamera-Zugriff für visuelle Erkennung',
        'LSUIElement': True,
    },
    'includes': [
        # Projektspezifische Module
        'env_manager', 'ui', 'gemini_worker', 'config', 'utils',
        
        # Google Generative AI wird explizit einbezogen
        'google', 'google.generativeai', 'google.api_core', 'google.auth',
        
        # Grundlage für benötigte Module
        'PyQt5', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets',
        'cv2', 'PIL', 'pyaudio', 'mss', 'pynput', 'dotenv',
    ],
    
    # Aktiviere alias-Modus wenn angefordert
    'alias': ALIAS,
    
    # Vollständiger Standalone-Modus, wenn nicht alias
    'site_packages': not ALIAS,
    'strip': not ALIAS,
}

setup(
    app=APP,
    name="Gemini Assistant",
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
    install_requires=open('requirements.txt').read().splitlines(),
)