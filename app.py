"""
## Documentation
Quickstart: https://github.com/google-gemini/cookbook/blob/main/quickstarts/Get_started_LiveAPI.py

## Setup

To install the dependencies for this script, run:

```
pip install google-genai opencv-python pyaudio pillow mss PyQt5 py2app pynput python-dotenv
```
"""

import sys
import objc
from pynput import keyboard
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from AppKit import NSApplication

from config import HOTKEY_COMBINATION, current_keys
from ui import CompactGeminiAppWindow

def on_press(key):
    try:
        current_keys.add(key)
        if all(k in current_keys for k in HOTKEY_COMBINATION):
            # Show the app window when hotkey is pressed
            if window.isVisible():
                window.hide_and_stop_listening()
            else:
                window.force_show_window()
    except:
        pass

def on_release(key):
    try:
        current_keys.discard(key)
    except:
        pass

if __name__ == "__main__":
    # Set Qt attributes before creating QApplication
    if sys.platform == "darwin":  # macOS specific
        QApplication.setAttribute(Qt.AA_DisableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_MacPluginApplication, True)
    
    # Initialize QApplication
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Keep running when window is closed
    
    try:
        # For macOS: Hide the dock icon properly using PyObjC
        if sys.platform == "darwin":
            try:
                # Try PyObjC approach:
                from Foundation import NSBundle
                info = NSBundle.mainBundle().infoDictionary()
                info["LSBackgroundOnly"] = "1"
                
                # Additional approach - more radical
                NSApplication.sharedApplication().setActivationPolicy_(1)  # NSApplicationActivationPolicyAccessory
            except ImportError:
                # If PyObjC is not available, we already used Qt approach as fallback
                pass
        
        # Create main window - API-Key wird nun über die UI in den Einstellungen verwaltet
        window = CompactGeminiAppWindow()
        
        # Setup global hotkey listener
        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()
        
        # Start event loop
        sys.exit(app.exec_())
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
