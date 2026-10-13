import re, unicodedata
from .inference import fingerprint, ready

def folded(s):return ''.join(c for c in unicodedata.normalize('NFD',s.lower()) if unicodedata.category(c)!='Mn')

def search(store,encoder,query='',filters=None,query_input=None):
    import numpy as np
    filters=filters or {};where=['l.enabled=1'];args=[]
    if not filters.get('offline',True):where.append('l.online=1')
    lids=filters.get('locations')
    if lids:
        locations=store.locations();selected=[l for l in locations if l['id'] in lids]
        from pathlib import Path
        lids=list(set(lids)|{l['id'] for l in locations for parent in selected if l['volume']==parent['volume'] and Path(l['path']).is_relative_to(Path(parent['path']))})
    if lids is not None:
        if not lids:return {'results':[],'mode':'Sin ubicaciones en este ámbito','warning':''}
        where.append('f.location_id IN ('+','.join('?' for _ in lids)+')');args+=lids
    if filters.get('volume'):where.append('l.volume=?');args.append(filters['volume'])
    if filters.get('folder'):
        folder=filters['folder'].rstrip('/')
        where.append("(f.path=? OR substr(f.path,1,?)=?)");args += [folder,len(folder)+1,folder+'/']
    if filters.get('kind'):where.append('f.kind=?');args.append(filters['kind'])
    if filters.get('important'):where.append('f.important=1')
    for key,op in [('min_size','>='),('max_size','<=')]:
        if filters.get(key) is not None:where.append('f.size'+op+'?');args.append(int(filters[key]))
    if filters.get('after'):where.append('f.mtime_ns>=?');args.append(int(filters['after']*1e9))
    with store.connect() as c:
        sql='SELECT f.*,l.name AS location_name,l.online,l.volume FROM files f JOIN locations l ON l.id=f.location_id WHERE '+' AND '.join(where)
        rows={r['id']:dict(r) for r in c.execute(sql,args)}
        if not rows:return {'results':[],'matching':0,'mode':'Sin archivos incluidos','warning':'No hay archivos indexados en este ámbito. Activa una carpeta o disco, o espera al escaneo inicial.'}
        # Join with the same exact filters before reading vector BLOBs.
        segments=c.execute('SELECT s.* FROM segments s JOIN files f ON s.file_id=f.id JOIN locations l ON l.id=f.location_id WHERE '+' AND '.join(where),args)
        settings=store.settings();qvec=None;warning='';mode='Por nombre y texto'
        if (query.strip() or query_input) and ready():
            try:
                items=[]
                if query.strip():items.append({'modality':'text','value':query})
                if query_input:items.append(query_input)
                vectors=[np.frombuffer(v,dtype='<f4') for v in encoder.encode(items,settings,query=True)]
                qvec=np.mean(vectors,axis=0);norm=np.linalg.norm(qvec)
                if norm<1e-8 or not np.isfinite(qvec).all():raise ValueError('Consulta sin representación válida.')
                qvec=qvec/norm
                mode='Por '+({'image':'imagen','audio':'audio'}[query_input['modality']] if query_input else 'texto')+' · semántica'
            except Exception as exc:
                if query_input:raise ValueError('No se pudo buscar con ese archivo: '+str(exc))
                warning=str(exc)
        elif query_input:raise ValueError('La búsqueda por imagen/audio requiere el modelo descargado.')
        elif query.strip():warning='Modelo descargándose. Por ahora se busca por nombre y texto extraído.'
        scores={};reasons={};positions={}
        tokens=folded(query).split()
        for fid,row in rows.items():
            name=folded(row['name']);text=folded(row['excerpt'])
            hits=sum(t in name for t in tokens);text_hits=sum(t in text for t in tokens)
            if not tokens:score=0
            else:score=.25*hits/len(tokens)+.1*text_hits/len(tokens)+(.35 if folded(query) in name else 0)
            scores[fid]=score;reasons[fid]='Nombre/texto' if score else 'Metadatos'
        lexical=dict(scores)
        if qvec is not None:
            model=fingerprint(settings['dimensions'])
            for seg in segments:
                if seg['model']!=model or seg['dim']!=len(qvec):continue
                v=np.frombuffer(seg['vector'],dtype='<f4');similarity=float(v@qvec)
                score=similarity+min(lexical.get(seg['file_id'],0),.3)
                if score>scores[seg['file_id']]:
                    scores[seg['file_id']]=score;positions[seg['file_id']]=seg['position'];reasons[seg['file_id']]={'text':'Texto','image':'Imagen','audio':'Audio'}[seg['modality']]
        results=[]
        for fid,r in rows.items():
            if tokens and qvec is None and scores[fid]<=0:continue
            r.update(score=scores[fid],reason=reasons[fid],match_position=positions.get(fid));results.append(r)
        sort=filters.get('sort','relevance')
        key=(lambda r:r['size']) if sort=='size' else (lambda r:r['mtime_ns']) if sort=='date' else (lambda r:r['opens']) if sort=='usage' else (lambda r:(r['score'],r['mtime_ns']))
        results.sort(key=key,reverse=True)
        return {'results':results[:100],'mode':mode,'warning':warning,'matching':len(results)}
