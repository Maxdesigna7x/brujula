"""Real-model smoke/regression check on synthetic files; no personal data."""
import json, os, sys, tempfile, time, subprocess, wave, math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image,ImageDraw
from embedding_app.inference import Encoder,ready
from embedding_app.storage import Store
from embedding_app.volumes import add_location
from embedding_app.indexer import Indexer
from embedding_app.search import search
root=Path(__file__).resolve().parents[1]
if not ready():raise SystemExit('Modelo pendiente; reanuda la descarga antes de probar.')
encoder=Encoder();settings=Store(root/'work/validation-settings').settings();report={}
try:
    start=time.monotonic()
    passages=['Un manual para instalar Linux y configurar el sistema operativo Ubuntu en una computadora.','Una receta de cocina para preparar pastel de chocolate con harina y huevos.']
    docs=[np.frombuffer(v,dtype='<f4') for v in encoder.encode([{'modality':'text','value':v} for v in passages],settings)]
    q=np.frombuffer(encoder.encode([{'modality':'text','value':'Cómo instalar Linux en mi PC'}],settings,query=True)[0],dtype='<f4')
    sims=[float(q@v) for v in docs]
    assert sims[0]>sims[1],sims
    assert all(np.isfinite(v).all() and abs(np.linalg.norm(v)-1)<1e-5 for v in docs)
    report['text']={'similarities':sims,'elapsed':time.monotonic()-start,'worker':encoder.info.copy()}
    with tempfile.TemporaryDirectory(prefix='brujula-validation-') as directory:
        d=Path(directory);im=Image.new('RGB',(320,240),'skyblue');draw=ImageDraw.Draw(im);draw.rectangle((0,160,320,240),fill='green');draw.ellipse((220,20,280,80),fill='yellow');im.save(d/'paisaje.png')
        v=encoder.encode([{'modality':'image','value':str(d/'paisaje.png')}],settings)[0]
        assert len(v)==256*4;report['image']=encoder.info.copy()
        samples=(np.sin(np.arange(16000*3)*2*np.pi*440/16000)*.1*32767).astype('<i2')
        with wave.open(str(d/'tono.wav'),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(samples.tobytes())
        v=encoder.encode([{'modality':'audio','value':str(d/'tono.wav')}],settings)[0]
        assert len(v)==256*4;report['audio']=encoder.info.copy();encoder.close()
        (d/'manual_linux.txt').write_text(passages[0]);(d/'receta.txt').write_text(passages[1])
        subprocess.run(['ffmpeg','-nostdin','-v','error','-loop','1','-i',str(d/'paisaje.png'),'-i',str(d/'tono.wav'),'-t','3','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-y',str(d/'paisaje.mp4')],check=True,timeout=60)
        for p in d.iterdir():os.utime(p,(time.time()-20,time.time()-20))
        store=Store(root/'work/validation-index');lid=add_location(store,d)
        store.update_settings({'video_frames':2,'audio_windows':1,'audio_seconds':5})
        indexer=Indexer(store,encoder);indexer.run()
        with store.connect() as c:
            files=[dict(r) for r in c.execute('SELECT name,status,error FROM files')];report['indexed']=files
            assert all(r['status']=='ready' for r in files),files
        result=search(store,encoder,'Cómo instalar Ubuntu',{'locations':[lid],'kind':'text'})
        assert 'semántica' in result['mode'],result
        assert result['results'][0]['name']=='manual_linux.txt',result
        report['search']={'first':result['results'][0]['name'],'worker':encoder.info.copy()}
    report['ok']=True
finally:
    encoder.close();(root/'work/model-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False,indent=2))
