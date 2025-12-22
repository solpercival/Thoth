import sys
from pathlib import Path

# Fix import paths
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from whisper_client.system_audio_whisper_client import SystemAudioWhisperClient
from ollama_client.llm_client import OllamaClient
from flask import Flask


app = Flask(__name__)


# Your code here
@app.route('/')
def home():
    pass

if __name__ == "__main__":
    home()
