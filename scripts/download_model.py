"""Resumable download. Does not read or upload user documents."""
import os, time
from pathlib import Path
os.environ.setdefault('HF_HUB_DOWNLOAD_TIMEOUT', '120')
os.environ.setdefault('HF_HUB_ETAG_TIMEOUT', '120')
from huggingface_hub import snapshot_download
root = Path(__file__).resolve().parents[1]
for attempt in range(1, 13):
    try:
        print(f'Descargando EmbeddingGemma 2: intento {attempt}/12', flush=True)
        folder = snapshot_download('google/embeddinggemma-2', revision='914f7f89142e33e77833254d9c9b90c3cef7303b', local_dir=root / 'models' / 'embeddinggemma-2', max_workers=2, allow_patterns=['*.json','*.model','*.safetensors','*.jinja','README.md','1_Pooling/*','2_Normalize/*'])
        print(f'MODEL_READY {folder}', flush=True)
        break
    except Exception as exc:
        print(f'Descarga interrumpida: {exc}. Reintentando en 30 s.', flush=True)
        time.sleep(30)
else:
    raise SystemExit('No se pudo descargar. Ejecuta de nuevo scripts/download_model.py para reanudar.')
