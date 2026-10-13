"""Writable user paths stay separate from the editable, read-only application."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get('BRUJULA_DATA', Path(os.environ.get('XDG_DATA_HOME', Path.home()/'.local/share'))/'brujula'))
RUNTIME_STATE = DATA/'setup-state.json'
RUNTIME_CONFIG = DATA/'runtime.json'


def model_directory():
    if os.environ.get('BRUJULA_MODEL_DIR'):
        return Path(os.environ['BRUJULA_MODEL_DIR'])
    # Keep the source checkout and its existing downloaded model usable.
    if (ROOT/'models/embeddinggemma-2/config.json').exists():
        return ROOT/'models/embeddinggemma-2'
    return DATA/'models/embeddinggemma-2'


def engine_python():
    if os.environ.get('BRUJULA_ENGINE_PYTHON'):
        return Path(os.environ['BRUJULA_ENGINE_PYTHON'])
    developer = ROOT/'.venv/bin/python'
    if developer.exists():
        return developer
    try:
        configuration=json.loads(RUNTIME_CONFIG.read_text())
        python=Path(configuration['python'])
        if python.exists() and configuration.get('ready'):
            return python
    except (OSError,ValueError,KeyError):
        pass
    return None


def setup_state():
    try:return json.loads(RUNTIME_STATE.read_text())
    except (OSError,ValueError):return {'phase':'idle','message':'Motor de IA pendiente de preparación'}
