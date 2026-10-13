"""Resumable standalone model download to source checkout or user data."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from embedding_app.setup_ai import download_model
download_model()
