"""
Functions for managing environment variables in the .env file
"""

import os
from dotenv import load_dotenv, set_key, find_dotenv

# Standard file path for the .env file in the project directory
ENV_FILE = find_dotenv(usecwd=True)
if not ENV_FILE:
    # If no .env file was found, we create the path to the project directory
    ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')

def load_env_variables():
    """
    Loads environment variables from the .env file.
    Creates the .env file if it doesn't exist.
    """
    # Create the .env file if it doesn't exist
    if not os.path.exists(ENV_FILE):
        with open(ENV_FILE, 'w') as f:
            f.write("# Gemini Assistant Configuration\n")
            f.write("GEMINI_API_KEY=\n")
    
    # Load environment variables
    load_dotenv(ENV_FILE)
    
    return {
        'api_key': os.getenv('GEMINI_API_KEY', '')
    }

def save_api_key(api_key):
    """
    Saves the API key in the .env file.
    
    Args:
        api_key: The API key to save
    """
    set_key(ENV_FILE, 'GEMINI_API_KEY', api_key)
    # Update the current environment variable
    os.environ['GEMINI_API_KEY'] = api_key
    return True