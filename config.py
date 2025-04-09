"""
Configuration and globals for the Gemini Assistant application.
"""

import os
import sys
import pyaudio
from pynput import keyboard
from google import genai
from google.genai import types
from env_manager import load_env_variables

# Laden der Umgebungsvariablen aus der .env-Datei
env_vars = load_env_variables()

# Audio settings
FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

# Gemini settings
MODEL = "models/gemini-2.0-flash-exp"
DEFAULT_MODE = "camera"

# Get API key from environment or leave empty
GEMINI_API_KEY = env_vars.get('api_key', '')

# Client wird erst später initialisiert oder wenn ein API-Key existiert
client = None
if GEMINI_API_KEY:
    client = genai.Client(http_options={"api_version": "v1alpha"}, api_key=GEMINI_API_KEY)

# Gemini tools configuration
tools = [
    types.Tool(google_search=types.GoogleSearch()),
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="getWeather",
                description="gets the weather for a requested city",
                parameters=genai.types.Schema(
                        type = genai.types.Type.OBJECT,
                        properties = {
                            "city": genai.types.Schema(
                                type = genai.types.Type.STRING,
                            ),
                        },
                    ),
            ),
        ]
    ),
]

# Gemini connection configuration
CONFIG = types.LiveConnectConfig(
    response_modalities=[
        "text",
    ],
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")
        )
    ),
    tools=tools,
)

# Global PyAudio instance
pya = pyaudio.PyAudio()

# Global hotkey combination
HOTKEY_COMBINATION = {keyboard.Key.cmd, keyboard.Key.shift, keyboard.Key.space}
current_keys = set()

# Import for macOS text-to-speech
if sys.platform == "darwin":
    try:
        from Foundation import NSSpeechSynthesizer
        USE_NATIVE_TTS = True
    except ImportError:
        USE_NATIVE_TTS = False
else:
    USE_NATIVE_TTS = False

# Funktion, um den Client zu initialisieren oder zu aktualisieren
def get_or_create_client(api_key=None):
    global client
    
    # Wenn ein API-Key bereitgestellt wird, Client damit erstellen oder aktualisieren
    if api_key:
        client = genai.Client(http_options={"api_version": "v1alpha"}, api_key=api_key)
    # Wenn kein API-Key gegeben, aber bereits ein Client existiert
    elif client:
        return client
    # Ansonsten neuen Client ohne API-Key erstellen (wird später einen Fehler auslösen)
    else:
        # Erstelle einen "Dummy"-Client, der später aktualisiert werden kann
        client = genai.Client(http_options={"api_version": "v1alpha"})
        
    return client