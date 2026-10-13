import hashlib, json, os, tempfile, threading, time, uuid, stat
from pathlib import Path
from .readers import kind, SENSITIVE, text_samples, extract_media
from .inference import ready, fingerprint
from .paths import engine_python
from .volumes import refresh_locations
from .metadata import birth_time
from .resources import ResourceGate

class Indexer:
    def __init__(self,store,encoder):
        self.store=store;self.encoder=encoder;self.pause=threading.Event();self.stop=threading.Event();self.thread=None
        self.gate=ResourceGate()
        self.state={'running':False,'phase':'En espera','current':'','done':0,'total':0,'errors':0,'stage':'idle','scanned':0,'part_done':0,'part_total':0,'location':''}
    def start(self):
        if self.thread and self.thread.is_alive():self.stop.clear();self.pause.clear();return
        self.pause.clear();self.stop.clear();self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
    def wait(self):
        while self.pause.is_set() and not self.stop.is_set():time.sleep(.2)
        if self.stop.is_set():raise InterruptedError()
    def recipe(self,s):
        relevant={k:s[k] for k in ['dimensions','video_frames','audio_windows','audio_seconds','text_words','enable_audio','types','exclude']}
        return hashlib.sha256(json.dumps(relevant,sort_keys=True).encode()).hexdigest()+fingerprint(s['dimensions'])
    def scan(self,settings):
        refresh_locations(self.store)
        locations=self.store.locations()
        for loc in locations:
            if not loc['online'] or not loc['enabled']:continue
            self.state['location']=loc['name']
            token=uuid.uuid4().hex;failures=[];excluded=set(settings['exclude']);base=Path(loc['path']);device=base.stat().st_dev
            # Existing child locations retain their records, tags and zones.
            covered=[Path(other['path']) for other in locations if other['id']!=loc['id'] and Path(other['path']).is_relative_to(base)]
            def allowed_directory(path):
                if path in covered or path.is_symlink():return False
                if base==Path('/') and path in [Path('/proc'),Path('/sys'),Path('/dev'),Path('/run'),Path('/tmp')]:return False
                try:return path.stat().st_dev==device
                except OSError as exc:failures.append(str(exc));return False
            for directory,dirs,files in os.walk(base,followlinks=False,onerror=lambda e:failures.append(str(e))):
                self.wait()
                dirs[:]=[d for d in dirs if not d.startswith('.') and d not in excluded and allowed_directory(Path(directory)/d)]
                with self.store.connect() as c:
                    for name in files:
                        p=Path(directory)/name
                        if name.startswith('.') or p.is_symlink() or p.suffix.lower() in SENSITIVE or name in {'id_rsa','id_ed25519','credentials','credentials.json'}:continue
                        try:
                            st=p.stat()
                            if st.st_dev!=device or not stat.S_ISREG(st.st_mode):continue
                            category=kind(p)
                            if category not in settings['types']:continue
                            self.state['scanned']+=1;self.state['current']=name
                            rel=str(p.relative_to(base));old=c.execute('SELECT id,size,mtime_ns FROM files WHERE location_id=? AND relative=?',(loc['id'],rel)).fetchone()
                            if old:
                                changed=st.st_size!=old['size'] or st.st_mtime_ns!=old['mtime_ns']
                                c.execute('UPDATE files SET path=?,size=?,mtime_ns=?,seen=? WHERE id=?',(str(p),st.st_size,st.st_mtime_ns,token,old['id']))
                                if changed:
                                    c.execute('DELETE FROM segments WHERE file_id=?',(old['id'],));c.execute("UPDATE files SET status='pending',error='',excerpt='',recipe='' WHERE id=?",(old['id'],))
                            else:
                                c.execute('INSERT INTO files(location_id,relative,path,name,kind,size,mtime_ns,btime,seen) VALUES (?,?,?,?,?,?,?,?,?)',(loc['id'],rel,str(p),name,category,st.st_size,st.st_mtime_ns,birth_time(p),token))
                        except OSError as exc:failures.append(str(exc))
            # Never purge a partially scanned or disconnected volume.
            if not failures and base.is_dir():
                refresh_locations(self.store)
                online=next(x['online'] for x in self.store.locations() if x['id']==loc['id'])
                if online:
                    with self.store.connect() as c:
                        c.execute('DELETE FROM segments WHERE file_id IN (SELECT id FROM files WHERE location_id=? AND seen<>?)',(loc['id'],token))
                        c.execute('DELETE FROM files WHERE location_id=? AND seen<>?',(loc['id'],token))
            for error in failures[:10]:self.store.log('Escaneo incompleto: '+error)
    def run(self):
        self.state.update(running=True,phase='Leyendo metadatos',stage='scan',done=0,total=0,errors=0,scanned=0,part_done=0,part_total=0,current='',location='')
        try:
            s=self.store.settings();recipe=self.recipe(s);self.scan(s)
            if not ready() or not engine_python():
                self.state.update(phase='Extrayendo texto sin modelo',stage='metadata')
                with self.store.connect() as c:
                    texts=[dict(r) for r in c.execute("SELECT f.* FROM files f JOIN locations l ON f.location_id=l.id WHERE f.kind='text' AND f.excerpt='' AND l.online=1 AND l.enabled=1")]
                for f in texts:
                    self.wait()
                    try:
                        excerpt=text_samples(f['path'],int(s['text_words']))
                        with self.store.connect() as c:c.execute('UPDATE files SET excerpt=? WHERE id=?',(excerpt[:20000],f['id']))
                    except Exception:pass  # Detailed extraction errors recorded during full index pass.
                self.state.update(phase='Metadatos listos · esperando el modelo',stage='waiting_model');return
            with self.store.connect() as c:
                files=[dict(r) for r in c.execute("SELECT f.*,l.name AS location_name FROM files f JOIN locations l ON f.location_id=l.id WHERE l.online=1 AND l.enabled=1 AND (f.status='pending' OR f.recipe<>?) ORDER BY CASE f.kind WHEN 'text' THEN 0 WHEN 'image' THEN 1 ELSE 2 END,f.size",(recipe,))]
            self.state.update(total=len(files),phase='Analizando contenido',stage='index',current='')
            for f in files:
                self.wait();self.state.update(current=f['name'],location=f.get('location_name',''),part_done=0,part_total=0);p=Path(f['path'])
                self.gate.wait(self.store.settings,self.encoder,self.state,self.wait)
                try:
                    before=p.stat()
                    # Do not index files that are still arriving/downloading.
                    if time.time()-before.st_mtime<5:continue
                    self.state['phase']='Preparando muestras'
                    items=[{'modality':'text','value':f['name'],'position':None}];excerpt=''
                    with tempfile.TemporaryDirectory(prefix='brujula-') as tmp:
                        if f['kind']=='text':
                            excerpt=text_samples(p,int(s['text_words']))
                            with self.store.connect() as c:c.execute('UPDATE files SET excerpt=? WHERE id=?',(excerpt[:20000],f['id']))
                            words=excerpt.split()
                            items += [{'modality':'text','value':f['name']+'\n'+' '.join(words[i:i+650]),'position':None} for i in range(0,len(words),650)]
                        elif f['kind']=='image':items.append({'modality':'image','value':str(p),'position':None})
                        elif f['kind'] in ('video','audio'):
                            items += [{'modality':m,'value':v,'position':t} for m,v,t in extract_media(p,f['kind'],s,tmp)]
                        vectors=[];self.state.update(part_total=len(items),phase='Analizando contenido')
                        for item in items:
                            self.wait();self.gate.wait(self.store.settings,self.encoder,self.state,self.wait)
                            effective=dict(s);effective['device']=self.store.settings()['device']
                            vectors+=self.encoder.encode([item],effective)
                            self.state['part_done']+=1
                    after=p.stat()
                    if after.st_size!=before.st_size or after.st_mtime_ns!=before.st_mtime_ns:continue
                    with self.store.connect() as c:
                        c.execute('DELETE FROM segments WHERE file_id=?',(f['id'],))
                        for item,v in zip(items,vectors):c.execute('INSERT INTO segments(file_id,modality,position,vector,dim,model) VALUES (?,?,?,?,?,?)',(f['id'],item['modality'],item['position'],v,s['dimensions'],fingerprint(s['dimensions'])))
                        c.execute("UPDATE files SET status='ready',error='',excerpt=?,recipe=? WHERE id=?",(excerpt[:20000],recipe,f['id']))
                except Exception as exc:
                    self.state['errors']+=1;self.store.log(f"{f['name']}: {exc}")
                    with self.store.connect() as c:c.execute("UPDATE files SET status='error',error=?,recipe=? WHERE id=?",(str(exc),recipe,f['id']))
                finally:self.state['done']+=1;self.state['part_done']=0;self.state['part_total']=0
            self.state.update(phase='Índice actualizado',stage='complete')
        except InterruptedError:self.state.update(phase='Detenido',stage='stopped')
        except Exception as exc:self.state.update(phase='Error: '+str(exc),stage='error');self.store.log(str(exc))
        finally:
            self.state['running']=False;self.state['current']='';self.encoder.close()
