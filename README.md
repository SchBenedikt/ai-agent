# Gemini Assistant macOS App
A native macOS application that connects to Google's Gemini AI. The app automatically accesses your camera and microphone to provide a seamless AI assistant experience.
![image](https://github.com/user-attachments/assets/8fa117b0-f19a-4aca-a684-619789f2af1d)

## Features
- Audio input through your microphone
- Visual context through your camera
- Text responses displayed in the app
- Audio responses played through your speakers

## Setup

### Prerequisites
1. Python 3.8+
2. A Google Gemini API key

### Installation
1. Install the required dependencies:
   ```
   pip install google-generativeai opencv-python pyaudio pillow mss PyQt5 pynput python-dotenv pyinstaller
   ```

2. Set your Gemini API key as an environment variable (optional):
   ```
   export GEMINI_API_KEY="your-api-key-here"
   ```
   If not set as an environment variable, the app will ask for it on startup.

### Building the macOS App

There are two ways to build the app:

#### Method 1: Using PyInstaller (Recommended)
PyInstaller creates a more reliable standalone application that better handles dependencies:

1. Make sure PyInstaller is installed:
   ```
   pip install pyinstaller
   ```

2. Run the build process:
   ```
   # First clean any previous builds
   rm -rf build dist
   
   # Create the app bundle using the spec file
   pyinstaller gemini.spec
   ```

3. The app will be created as `Gemini Assistant.app` in the `dist` folder

#### Method 2: Using py2app (Alternative)
This method may have issues with certain dependencies:

1. Make sure py2app is installed:
   ```
   pip install py2app
   ```

2. Run the build process:
   ```
   # First clean any previous builds
   rm -rf build dist
   
   # Create the app bundle
   python setup.py py2app --alias
   ```

3. The app will be created in the `dist` folder. Using the `--alias` flag creates a development version that's easier to build.

### Running Without Building
To run directly without building:
```
python app.py
```

## Usage
1. Launch the app
2. Grant camera and microphone permissions when prompted
3. The app will automatically start listening and capturing video
4. Click the button to toggle listening on/off

## Troubleshooting

### Common Issues
- **Missing Modules**: If you encounter "No module named 'xyz'" errors, install the missing dependency with `pip install xyz`
- **Permission Issues**: If camera or microphone access doesn't work, check your macOS privacy settings
- **Build Errors**: If PyInstaller fails with recursion errors, try using the '--debug' flag to identify problematic dependencies

### Building Tips
- The PyInstaller spec file (`gemini.spec`) is configured to include all necessary dependencies
- For development, the alias mode (`--alias`) creates a simpler app bundle that points to your source files
- For distribution, use the default (non-alias) mode to create a completely standalone application
