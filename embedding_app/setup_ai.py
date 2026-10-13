"""Explicit, resumable first-run setup. No root privileges or source edits."""
import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from .paths import ROOT, DATA, RUNTIME_STATE, RUNTIME_CONFIG, model_directory

REVISION='914f7f89142e33e77833254d9c9b90c3cef7303b'
WEIGHT_SHA='197a32965d4b1105faf060417baa899e193fb73cd401f42ec9295234d5553d79'
WEIGHT_BYTES=1488915288


def state(phase,message,**extra):
    DATA.mkdir(parents=True,exist_ok=True)
    temporary=RUNTIME_STATE.with_suffix('.tmp')
    temporary.write_text(json.dumps({'phase':phase,'message':message,'updated':time.time(),**extra},ensure_ascii=False))
    temporary.replace(RUNTIME_STATE)
    print(message,file=sys.stderr,flush=True)


def command(args):
    subprocess.run([str(a) for a in args],check=True)


def download_model():
    os.environ.setdefault('HF_HUB_DOWNLOAD_TIMEOUT','120')
    os.environ.setdefault('HF_HUB_ETAG_TIMEOUT','120')
    from huggingface_hub import snapshot_download
    destination=model_directory()
    for attempt in range(1,13):
        try:
            state('model',f'Descargando modelo · intento {attempt}/12',expected_bytes=WEIGHT_BYTES)
            snapshot_download('google/embeddinggemma-2',revision=REVISION,local_dir=destination,max_workers=2,
                              allow_patterns=['*.json','*.model','*.safetensors','*.jinja','README.md','1_Pooling/*','2_Normalize/*'])
            state('verify','Verificando integridad del modelo')
            with (destination/'model.safetensors').open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
            if digest!=WEIGHT_SHA:raise ValueError('El modelo descargado no coincide con SHA-256. Revisa la descarga antes de continuar.')
            state('complete','IA preparada · modelo verificado',model=str(destination))
            return
        except Exception as exc:
            if attempt==12:raise
            state('model',f'Descarga interrumpida: {exc}. Reintento en 30 segundos.',expected_bytes=WEIGHT_BYTES)
            time.sleep(30)


def prepare(mode):
    directory=DATA/('runtime-'+mode)
    python=directory/'bin/python'
    existing=ROOT/'.venv/bin/python'
    if existing.exists():
        python=existing
        state('runtime','Reutilizando el entorno de desarrollo existente')
    else:
        state('runtime','Preparando entorno privado de Python')
        if not python.exists():command([sys.executable,'-m','venv',directory])
        state('runtime','Descargando PyTorch '+('CPU' if mode=='cpu' else 'CUDA · descarga grande'))
        index='https://download.pytorch.org/whl/'+('cpu' if mode=='cpu' else 'cu130')
        command([python,'-m','pip','install','--timeout','120','--retries','8','torch==2.12.0','torchvision==0.27.0','--index-url',index])
        state('runtime','Instalando dependencias de búsqueda y documentos')
        command([python,'-m','pip','install','--timeout','120','--retries','8','-r',ROOT/'requirements-runtime.txt'])
    state('runtime','Comprobando el motor de inferencia')
    command([python,ROOT/'scripts/check_runtime.py'])
    from .storage import Store
    Store().update_settings({'device':'cpu' if mode=='cpu' else 'auto'})
    config={'ready':True,'python':str(python),'mode':mode,'prepared':time.time(),'app_version':'0.2.0'}
    temporary=RUNTIME_CONFIG.with_suffix('.tmp');temporary.write_text(json.dumps(config));temporary.replace(RUNTIME_CONFIG)
    # Re-exec the download in the prepared runtime; it contains Hugging Face.
    state('model','Motor preparado · iniciando descarga del modelo')
    command([python,'-m','embedding_app.setup_ai','--download-only'])


def main():
    # Closing the owning setup process also terminates its pip/download child.
    if sys.platform=='linux':
        import ctypes,signal
        ctypes.CDLL(None).prctl(1,signal.SIGTERM)
        if os.getppid()==1:return
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['cpu','cuda'],default='cpu');parser.add_argument('--download-only',action='store_true');args=parser.parse_args()
    DATA.mkdir(parents=True,exist_ok=True)
    lock=None
    if not args.download_only:
        lock=(DATA/'setup.lock').open('a')
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit('Ya hay una preparación en curso.')
    try:
        if args.download_only:download_model()
        else:prepare(args.mode)
    except Exception as exc:
        state('error','No se pudo completar la preparación: '+str(exc));raise

if __name__=='__main__':main()
