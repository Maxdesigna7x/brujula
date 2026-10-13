#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
python -m venv --system-site-packages .venv
# Use the existing CUDA installation when available; do not redownload torch.
if .venv/bin/python -c 'import torch; import scipy; import sklearn; import numpy; import PIL; import docx' 2>/dev/null; then
  UV_NATIVE_TLS=true uv pip install --python .venv/bin/python --no-deps 'transformers==5.19.0' 'sentence-transformers==6.1.0' 'pypdf>=6' 'soundfile>=0.13' 'tokenizers==0.23.3' 'safetensors==0.8.0'
else
  UV_NATIVE_TLS=true uv pip install --python .venv/bin/python -r requirements.txt
fi
.venv/bin/python scripts/check_runtime.py
printf '%s\n' 'Entorno preparado. Descarga: .venv/bin/python scripts/download_model.py' 'Abrir: ./run.sh'
