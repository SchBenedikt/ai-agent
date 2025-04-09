"""
Funktionen zum Verwalten der Umgebungsvariablen in der .env-Datei
"""

import os
from dotenv import load_dotenv, set_key, find_dotenv

# Standard-Dateipfad für die .env-Datei im Projektverzeichnis
ENV_FILE = find_dotenv(usecwd=True)
if not ENV_FILE:
    # Wenn keine .env-Datei gefunden wurde, erstellen wir den Pfad zum Projektverzeichnis
    ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')

def load_env_variables():
    """
    Lädt die Umgebungsvariablen aus der .env-Datei.
    Erstellt die .env-Datei, falls sie nicht existiert.
    """
    # Erstellen der .env-Datei, wenn sie nicht existiert
    if not os.path.exists(ENV_FILE):
        with open(ENV_FILE, 'w') as f:
            f.write("# Gemini Assistant Konfiguration\n")
            f.write("GEMINI_API_KEY=\n")
    
    # Laden der Umgebungsvariablen
    load_dotenv(ENV_FILE)
    
    return {
        'api_key': os.getenv('GEMINI_API_KEY', '')
    }

def save_api_key(api_key):
    """
    Speichert den API-Key in der .env-Datei.
    
    Args:
        api_key: Der zu speichernde API-Key
    """
    set_key(ENV_FILE, 'GEMINI_API_KEY', api_key)
    # Aktualisieren der aktuellen Umgebungsvariable
    os.environ['GEMINI_API_KEY'] = api_key
    return True