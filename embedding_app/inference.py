"""Dedicated model process. JSON lines on stdin/stdout, diagnostics on stderr."""
import base64, hashlib, json, os, subprocess, sys, threading, time
from pathlib import Path
from .paths import ROOT, model_directory, engine_python
MODEL=model_directory()

def ready():
    return (MODEL/'model.safetensors').is_file() and (MODEL/'tokenizer.model').is_file() and (MODEL/'tokenizer.json').is_file()

def fingerprint(dim):
    config=(MODEL/'config.json').read_bytes() if (MODEL/'config.json').exists() else b'missing'
    metadata=MODEL/'.cache/huggingface/download/config.json.metadata'
    revision=metadata.read_text().splitlines()[0] if metadata.exists() else hashlib.sha256(config).hexdigest()[:16]
    return 'embeddinggemma-2:'+revision+':recipe1:mrl:'+str(dim)

class Encoder:
    def __init__(self):
        self.info={};self.process=None;self.lock=threading.RLock();self.last=0;self.options=None
    def close(self):
        with self.lock:
            if self.process:
                self.process.terminate()
                try:self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
                self.process=None
    def encode(self,items,settings,query=False):
        with self.lock:
            if not engine_python():raise RuntimeError('Prepara el motor de IA desde Configuración → Preparar IA.')
            if not ready():raise RuntimeError('El modelo sigue descargándose; la búsqueda por nombre ya funciona.')
            options=(settings['device'],settings['dimensions'])
            if self.process and (self.process.poll() is not None or options!=self.options):self.close()
            if not self.process:
                self.process=subprocess.Popen([str(engine_python()),'-m','embedding_app.inference','worker'],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,bufsize=1)
                self.options=options
            request={'items':items,'query':query,'device':settings['device'],'dim':settings['dimensions']}
            self.process.stdin.write(json.dumps(request)+'\n');self.process.stdin.flush()
            line=self.process.stdout.readline()
            if not line:self.close();raise RuntimeError('El proceso del modelo terminó; revisa el registro de errores.')
            reply=json.loads(line);self.last=time.monotonic()
            if 'error' in reply:raise RuntimeError(reply['error'])
            self.info=reply.get('info',{})
            return [base64.b64decode(v) for v in reply['vectors']]
    def idle(self,seconds):
        # Do not wait on an active inference from the status/UI thread.
        if self.lock.acquire(blocking=False):
            try:
                if self.process and time.monotonic()-self.last>seconds:self.close()
            finally:self.lock.release()

def worker():
    # Model process cannot survive its owning backend and leak GPU memory.
    if sys.platform=='linux':
        import ctypes, signal
        ctypes.CDLL(None).prctl(1, signal.SIGTERM)
        if os.getppid()==1:return
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    model=None;mode=None
    for line in sys.stdin:
        try:
            req=json.loads(line);started=time.monotonic()
            with __import__('contextlib').redirect_stdout(sys.stderr):
                import numpy as np
                import torch
                from sentence_transformers import SentenceTransformer
                torch.set_num_threads(2)
                multimodal=any(i['modality']!='text' for i in req['items'])
                wanted='full' if multimodal else 'text'
                if model is None or (wanted=='full' and mode=='text'):
                    if model is not None:
                        del model;model=None;__import__('gc').collect()
                        if torch.cuda.is_available():torch.cuda.empty_cache()
                    device=req['device']
                    if device=='auto':device='cuda' if torch.cuda.is_available() else 'cpu'
                    dtype=torch.bfloat16 if device=='cuda' and torch.cuda.is_bf16_supported() else torch.float32
                    kwargs={} if multimodal else {'vision_config':None,'audio_config':None}
                    model=SentenceTransformer(str(MODEL),device=device,model_kwargs={'torch_dtype':dtype},config_kwargs=kwargs,local_files_only=True)
                    model.max_seq_length=4096;mode=wanted
                vectors=[]
                with torch.inference_mode():
                    for item in req['items']:
                        modality=item['modality'];value=item['value']
                        if modality=='text':
                            v=model.encode(value,prompt_name='query' if req['query'] else 'document',normalize_embeddings=True,convert_to_numpy=True,show_progress_bar=False)
                        else:
                            if modality=='audio':
                                import soundfile as sf
                                value,rate=sf.read(value,dtype='float32')
                                if value.ndim>1:value=value.mean(axis=1)
                                if rate!=16000:
                                    import math
                                    from scipy.signal import resample_poly
                                    divisor=math.gcd(rate,16000);value=resample_poly(value,16000//divisor,rate//divisor).astype(np.float32)
                            args={'processing_kwargs':{'image':{'max_soft_tokens':140}}} if modality=='image' else {}
                            v=model.encode({modality:value},normalize_embeddings=True,convert_to_numpy=True,show_progress_bar=False,**args)
                        v=np.asarray(v,dtype=np.float32).reshape(-1)[:req['dim']]
                        norm=np.linalg.norm(v)
                        if not np.isfinite(v).all() or norm==0:raise ValueError('Embedding inválido.')
                        vectors.append(base64.b64encode((v/norm).astype('<f4').tobytes()).decode())
            info={'seconds':time.monotonic()-started,'mode':mode,'device':str(model.device),'dtype':str(model.dtype),'peak_cuda_bytes':torch.cuda.max_memory_allocated() if torch.cuda.is_available() else 0,'reserved_cuda_bytes':torch.cuda.memory_reserved() if torch.cuda.is_available() else 0,'rss_bytes':int(Path('/proc/self/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE') if sys.platform=='linux' else None}
            print(json.dumps({'vectors':vectors,'info':info}),flush=True)
        except Exception as exc:
            __import__('traceback').print_exc(file=sys.stderr)
            print(json.dumps({'error':str(exc)}),flush=True)

if __name__=='__main__':worker()
