import json, subprocess
from pathlib import Path

def volumes():
    try:
        data=json.loads(subprocess.check_output(['lsblk','-J','-b','-o','NAME,LABEL,UUID,MOUNTPOINTS,SIZE,FSTYPE'],timeout=5))
        result=[]
        def visit(nodes):
            for n in nodes:
                if n.get('fstype') not in ('squashfs','swap',None):
                    for mount in n.get('mountpoints',[]):
                        if mount and not mount.startswith(('/boot','/snap')):
                            result.append({'uuid':n.get('uuid') or n['name'],'name':n.get('label') or ('Disco principal' if mount=='/' else n['name']),'mount':mount,'size':n['size']})
                visit(n.get('children',[]))
        visit(data['blockdevices']);return result
    except (OSError,ValueError,subprocess.SubprocessError):return []

def add_location(store,path,name=None):
    p=Path(path).expanduser().resolve()
    if not p.is_dir():raise ValueError('La carpeta no existe o no está disponible.')
    if str(p) in ('/','/proc','/sys','/dev','/run'):raise ValueError('Selecciona una carpeta de datos, no la raíz del sistema.')
    parent=None
    for loc in store.locations():
        old=Path(loc['path'])
        if p==old:return loc['id']
        if p.is_relative_to(old) and loc['relative'] in ('','.') and loc['mount']:
            parent=loc;continue
        if p.is_relative_to(old) or old.is_relative_to(p):
            raise ValueError('Esta carpeta se solapa con una ubicación existente. Usa zonas para agrupar sin duplicar.')
    disk=next((d for d in sorted(volumes(),key=lambda d:len(d['mount']),reverse=True) if p.is_relative_to(Path(d['mount']))),None)
    with store.connect() as c:
        cur=c.execute('INSERT INTO locations(path,name,volume,mount,relative) VALUES (?,?,?,?,?)',(str(p),name or p.name,disk['uuid'] if disk else '',disk['mount'] if disk else '',str(p.relative_to(disk['mount'])) if disk else ''))
        lid=cur.lastrowid
        if parent:
            prefix=str(p)+'/'
            for f in c.execute('SELECT id,path FROM files WHERE location_id=? AND substr(path,1,?)=?',(parent['id'],len(prefix),prefix)).fetchall():
                c.execute('UPDATE files SET location_id=?,relative=? WHERE id=?',(lid,str(Path(f['path']).relative_to(p)),f['id']))
        return lid

def refresh_locations(store):
    disks={v['uuid']:v for v in volumes()}
    with store.connect() as c:
        for loc in store.locations():
            if loc['volume']:
                disk=disks.get(loc['volume'])
                p=str(Path(disk['mount'])/loc['relative']) if disk else loc['path']
                online=bool(disk and Path(p).is_dir())
                if online and p!=loc['path']:
                    c.execute('UPDATE locations SET path=?,mount=? WHERE id=?',(p,disk['mount'],loc['id']))
                    for f in c.execute('SELECT id,relative FROM files WHERE location_id=?',(loc['id'],)).fetchall():
                        c.execute('UPDATE files SET path=? WHERE id=?',(str(Path(p)/f['relative']),f['id']))
            else:online=Path(loc['path']).is_dir()
            c.execute('UPDATE locations SET online=? WHERE id=?',(int(online),loc['id']))

def set_disk(store, volume_id, enabled):
    """Whole-volume root plus existing sublocations, without duplicate ownership."""
    disk=next((d for d in volumes() if d['uuid']==volume_id),None)
    locations=[l for l in store.locations() if l['volume']==volume_id]
    root=next((l for l in locations if l['relative'] in ('','.') and l['mount']),None)
    if enabled and root is None:
        if disk is None:raise ValueError('Conecta el disco para incluirlo por primera vez.')
        mount=Path(disk['mount']).resolve()
        if not mount.is_dir():raise ValueError('El disco no está disponible.')
        with store.connect() as c:
            c.execute('INSERT INTO locations(path,name,volume,mount,relative) VALUES (?,?,?,?,?)',
                      (str(mount),disk['name']+' · disco completo',volume_id,str(mount),'.'))
    with store.connect() as c:c.execute('UPDATE locations SET enabled=? WHERE volume=?',(int(enabled),volume_id))


def disk_states(store):
    disks=volumes();locations=store.locations()
    known={d['uuid'] for d in disks}
    for loc in locations:
        if loc['volume'] and loc['volume'] not in known:
            disks.append({'uuid':loc['volume'],'name':loc['name'].replace(' · disco completo',''),
                          'mount':loc['mount'],'size':0,'online':False})
            known.add(loc['volume'])
    for disk in disks:
        included=[l for l in locations if l['volume']==disk['uuid'] and l['enabled']]
        disk['online']=disk.get('online',True)
        disk['whole']=any(l['relative'] in ('','.') and l['mount'] for l in included) and all(l['enabled'] for l in locations if l['volume']==disk['uuid'])
        disk['partial']=bool(included) and not disk['whole']
        disk['included']=bool(included);disk['location_count']=len(included)
    return disks
