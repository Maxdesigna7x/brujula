import argparse, json, os, sys, threading, time, fcntl, tempfile, subprocess
from pathlib import Path
from .storage import Store
from .volumes import volumes, add_location, refresh_locations, set_disk, disk_states
from .inference import Encoder, ready, MODEL
from .indexer import Indexer
from .search import search

class Backend:
    def __init__(self,store=None):
        self.store=store or Store();self.encoder=Encoder();self.indexer=Indexer(self.store,self.encoder);self.end=threading.Event()
        self.last_scan=time.monotonic();self.was_ready=ready()
        self.scheduler=threading.Thread(target=self.maintenance,daemon=True);self.scheduler.start()
    def maintenance(self):
        while not self.end.wait(5):
            settings=self.store.settings();self.encoder.idle(settings['idle_seconds'])
            model_ready=ready();new_model=model_ready and not self.was_ready;self.was_ready=model_ready
            if not self.indexer.state['running'] and not self.indexer.pause.is_set() and (new_model or time.monotonic()-self.last_scan>int(settings['scan_minutes'])*60):
                self.last_scan=time.monotonic();self.indexer.start()
    def dispatch(self,op,**p):
        if op=='status':
            with self.store.connect() as c:
                counts={r['status']:r['n'] for r in c.execute('SELECT status,count(*) n FROM files GROUP BY status')}
                total=c.execute('SELECT count(*),coalesce(sum(size),0) FROM files').fetchone()
                events=[dict(r) for r in c.execute('SELECT time,message FROM events ORDER BY id DESC LIMIT 20')]
            return {'index':dict(self.indexer.state),'gpu':self.indexer.gate.last,'paused':self.indexer.pause.is_set(),'model_ready':ready(),'model_bytes':(MODEL/'model.safetensors').stat().st_size if ready() else sum(x.stat().st_size for x in MODEL.glob('.cache/huggingface/download/*.incomplete')),'locations':self.store.locations(),'zones':self.store.zones(),'volumes':disk_states(self.store),'counts':counts,'files':total[0],'bytes':total[1],'settings':self.store.settings(),'events':events}
        if op=='add_location':
            self.stop_index_for_change()
            lid=add_location(self.store,p['path'],p.get('name'));self.indexer.start();return {'id':lid}
        if op=='set_disk':
            self.stop_index_for_change();set_disk(self.store,p['volume'],bool(p['enabled']));self.indexer.start();return True
        if op=='set_location':
            self.stop_index_for_change()
            with self.store.connect() as c:c.execute('UPDATE locations SET enabled=? WHERE id=?',(int(bool(p['enabled'])),int(p['id'])))
            self.indexer.start();return True
        if op=='remove_location':
            if self.indexer.state['running']:raise ValueError('Detén la indexación antes de quitar una ubicación.')
            self.store.remove_location(int(p['id']));return True
        if op=='zone':return self.store.zone(p['name'],p['locations'])
        if op=='remove_zone':
            with self.store.connect() as c:c.execute('DELETE FROM zone_locations WHERE zone_id=?',(p['id'],));c.execute('DELETE FROM zones WHERE id=?',(p['id'],))
            return True
        if op=='settings':
            if p.get('values'):
                s=p['values']
                limits={'dimensions':(128,768),'video_frames':(1,48),'audio_windows':(1,12),'audio_seconds':(5,30),'text_words':(300,6000),'scan_minutes':(1,1440),'idle_seconds':(15,1800),'gpu_check_seconds':(10,3600),'gpu_max_utilization':(0,100),'gpu_min_free_mb':(256,100000)}
                for k,(lo,hi) in limits.items():
                    if k in s and not lo<=int(s[k])<=hi:raise ValueError('Valor fuera de rango: '+k)
                if 'dimensions' in s and s['dimensions'] not in (128,256,512,768):raise ValueError('Dimensiones no soportadas.')
                if s.get('device','auto') not in ('auto','cpu','cuda'):raise ValueError('Dispositivo inválido.')
                return self.store.update_settings(s)
            return self.store.settings()
        if op=='search':
            media=p.get('query_input')
            if not media:return search(self.store,self.encoder,p.get('query',''),p.get('filters'))
            modality=media.get('modality');path=Path(media.get('path','')).expanduser().resolve()
            if modality not in ('image','audio') or not path.is_file():raise ValueError('Selecciona una imagen o audio local válido.')
            if modality=='image':
                if path.stat().st_size>50_000_000:raise ValueError('La imagen debe pesar menos de 50 MB.')
                from PIL import Image, ImageOps
                with tempfile.TemporaryDirectory(prefix='brujula-query-') as tmp:
                    image_path=Path(tmp)/'query.jpg'
                    with Image.open(path) as image:
                        image=ImageOps.exif_transpose(image);image.thumbnail((1024,1024));image.convert('RGB').save(image_path)
                    return search(self.store,self.encoder,p.get('query',''),p.get('filters'),{'modality':'image','value':str(image_path)})
            with tempfile.TemporaryDirectory(prefix='brujula-query-') as tmp:
                audio_path=Path(tmp)/'query.wav'
                subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(path),'-t','30','-vn','-ac','1','-ar','16000','-y',str(audio_path)],check=True,timeout=30)
                return search(self.store,self.encoder,p.get('query',''),p.get('filters'),{'modality':'audio','value':str(audio_path)})
        if op=='thumbnails':
            from .thumbnails import thumbnail
            from concurrent.futures import ThreadPoolExecutor
            items=p.get('items',[])[:16]
            def one(item):return {'id':item['id'],'path':thumbnail(self.store,item['id'],item.get('position'))}
            with ThreadPoolExecutor(max_workers=3) as pool:return list(pool.map(one,items))
        if op=='start':self.last_scan=time.monotonic();self.indexer.start();return True
        if op=='pause':self.indexer.pause.set();return True
        if op=='stop':self.indexer.pause.set();self.indexer.stop.set();return True
        if op=='retry':
            with self.store.connect() as c:c.execute("UPDATE files SET status='pending' WHERE status='error'")
            self.indexer.start();return True
        if op=='important':
            with self.store.connect() as c:c.execute('UPDATE files SET important=? WHERE id=?',(int(p['value']),p['id']))
            return True
        if op=='opened':
            with self.store.connect() as c:c.execute('UPDATE files SET opens=opens+1,last_open=? WHERE id=?',(time.time(),p['id']))
            return True
        if op=='shutdown':self.close();return True
        raise ValueError('Operación desconocida.')
    def stop_index_for_change(self):
        self.indexer.stop.set();self.indexer.pause.clear()
        if self.indexer.thread and self.indexer.thread.is_alive():
            self.indexer.thread.join(timeout=30)
            if self.indexer.thread.is_alive():raise ValueError('El análisis actual está terminando. Vuelve a intentarlo en unos segundos.')
    def close(self):
        self.end.set();self.indexer.stop.set();self.indexer.pause.clear()
        # Closing encoder waits for the current inference, then actually returns memory.
        self.encoder.close()

def main():
    parser=argparse.ArgumentParser(description='Brújula: búsqueda local')
    parser.add_argument('--rpc',action='store_true');parser.add_argument('--daemon',action='store_true')
    sub=parser.add_subparsers(dest='command')
    add=sub.add_parser('add');add.add_argument('path');add.add_argument('--name')
    sub.add_parser('status');sub.add_parser('index')
    find=sub.add_parser('search');find.add_argument('query');find.add_argument('--location',type=int);find.add_argument('--kind',choices=['text','image','video','audio','other'])
    args=parser.parse_args();store=Store()
    lock=(store.directory/'backend.lock').open('a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise SystemExit('Brújula ya está abierta o tiene un servicio activo. Cierra esa instancia para usar la CLI.')
    b=Backend(store)
    try:
        if args.rpc:
            if store.locations():b.dispatch('start')
            for line in sys.stdin:
                try:
                    req=json.loads(line);op=req.pop('op');result=b.dispatch(op,**req);print(json.dumps({'result':result},ensure_ascii=False),flush=True)
                    if op=='shutdown':break
                except Exception as exc:print(json.dumps({'error':str(exc)},ensure_ascii=False),flush=True)
        elif args.daemon:
            b.dispatch('start')
            while True:time.sleep(1)
        elif args.command=='add':print(json.dumps(b.dispatch('add_location',path=args.path,name=args.name),ensure_ascii=False));b.indexer.thread.join()
        elif args.command=='index':b.dispatch('start');b.indexer.thread.join();print(json.dumps(b.dispatch('status'),ensure_ascii=False,indent=2))
        elif args.command=='search':
            filters={'kind':args.kind}
            if args.location:filters['locations']=[args.location]
            print(json.dumps(b.dispatch('search',query=args.query,filters=filters),ensure_ascii=False,indent=2))
        else:print(json.dumps(b.dispatch('status'),ensure_ascii=False,indent=2))
    finally:b.close()
if __name__=='__main__':main()
