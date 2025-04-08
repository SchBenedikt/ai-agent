# Gemini Assistant macOS App

A native macOS application that connects to Google's Gemini AI. The app automatically accesses your camera and microphone to provide a seamless AI assistant experience.

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
   pip install google-genai opencv-python pyaudio pillow mss PyQt5 py2app
   ```

2. Set your Gemini API key as an environment variable (optional):
   ```
   export GEMINI_API_KEY="your-api-key-here"
   ```
   If not set as an environment variable, the app will ask for it on startup.

### Building the App

To build a standalone macOS app:

```
python setup.py py2app
```

This will create a standalone app in the `dist` folder.

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

If you encounter issues with camera or microphone access, check your macOS privacy settings to ensure the app has the necessary permissions.
