"""Small real-model performance probe, not a whole-library throughput promise."""
import json,sys,tempfile,wave,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image
from embedding_app.inference import Encoder
from embedding_app.storage import DEFAULTS
root=Path(__file__).resolve().parents[1];e=Encoder();s=dict(DEFAULTS);report={}
try:
    e.encode([{'modality':'text','value':'Un documento sobre instalar Linux.'}],s)
    e.encode([{'modality':'text','value':'instalar Linux'}],s,query=True);report['query_warm']=e.info.copy()
    words=('Instalar Linux permite configurar el escritorio, gestionar documentos y organizar archivos. '*60)
    e.encode([{'modality':'text','value':words}],s);report['document_660_words']=e.info.copy()
    with tempfile.TemporaryDirectory() as d:
        d=Path(d);Image.new('RGB',(640,480),'green').save(d/'image.png')
        e.encode([{'modality':'image','value':str(d/'image.png')}],s);report['image_cold_multimodal']=e.info.copy()
        e.encode([{'modality':'image','value':str(d/'image.png')}],s);report['image_warm']=e.info.copy()
        tone=(np.sin(np.arange(16000*20)*2*np.pi*440/16000)*.1*32767).astype('<i2')
        with wave.open(str(d/'tone.wav'),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(tone.tobytes())
        e.encode([{'modality':'audio','value':str(d/'tone.wav')}],s);report['audio_20_seconds']=e.info.copy()
finally:e.close()
(root/'work/benchmark.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
