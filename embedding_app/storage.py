import json, os, sqlite3, time
from pathlib import Path
from .paths import DATA

DEFAULTS = {'profile':'Ligero','device':'auto','dimensions':256,'video_frames':12,'audio_windows':4,'audio_seconds':20,'text_words':3000,'enable_audio':True,'gpu_idle_only':True,'gpu_check_seconds':60,'gpu_max_utilization':15,'gpu_min_free_mb':2500,'scan_minutes':15,'idle_seconds':120,'theme':'system','exclude':['node_modules','.git','.venv','venv','__pycache__','models','work','.cache'], 'types':['text','image','video','audio','other']}

class Connection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()

class Store:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory else DATA
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory/'index.sqlite3'
        with self.connect() as c:
            c.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS locations(id INTEGER PRIMARY KEY,path TEXT UNIQUE NOT NULL,name TEXT NOT NULL,volume TEXT,mount TEXT,relative TEXT,enabled INTEGER DEFAULT 1,online INTEGER DEFAULT 1);
            CREATE TABLE IF NOT EXISTS zones(id INTEGER PRIMARY KEY,name TEXT UNIQUE NOT NULL);
            CREATE TABLE IF NOT EXISTS zone_locations(zone_id INTEGER,location_id INTEGER,PRIMARY KEY(zone_id,location_id));
            CREATE TABLE IF NOT EXISTS files(id INTEGER PRIMARY KEY,location_id INTEGER NOT NULL,relative TEXT NOT NULL,path TEXT NOT NULL,name TEXT NOT NULL,kind TEXT,size INTEGER,mtime_ns INTEGER,btime REAL,status TEXT DEFAULT 'pending',error TEXT DEFAULT '',excerpt TEXT DEFAULT '',important INTEGER DEFAULT 0,opens INTEGER DEFAULT 0,last_open REAL,seen TEXT,recipe TEXT DEFAULT '',UNIQUE(location_id,relative));
            CREATE INDEX IF NOT EXISTS files_location ON files(location_id);
            CREATE TABLE IF NOT EXISTS segments(id INTEGER PRIMARY KEY,file_id INTEGER NOT NULL,modality TEXT NOT NULL,position REAL,vector BLOB NOT NULL,dim INTEGER NOT NULL,model TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS segments_file ON segments(file_id);
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,time REAL,message TEXT);
            ''')
    def connect(self):
        c=sqlite3.connect(self.path, timeout=30, factory=Connection);c.row_factory=sqlite3.Row;return c
    def settings(self):
        s=dict(DEFAULTS)
        with self.connect() as c:
            for r in c.execute('SELECT * FROM settings'): s[r['key']]=json.loads(r['value'])
        return s
    def update_settings(self, values):
        with self.connect() as c:
            for k,v in values.items():
                if k not in DEFAULTS: raise ValueError('Ajuste desconocido: '+k)
                c.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',(k,json.dumps(v)))
        return self.settings()
    def log(self,message):
        with self.connect() as c:
            c.execute('INSERT INTO events(time,message) VALUES (?,?)',(time.time(),message))
            c.execute('DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT 200)')
    def locations(self):
        with self.connect() as c:return [dict(r) for r in c.execute('SELECT * FROM locations ORDER BY name')]
    def zones(self):
        with self.connect() as c:
            return [dict(r)|{'locations':[x[0] for x in c.execute('SELECT location_id FROM zone_locations WHERE zone_id=?',(r['id'],))]} for r in c.execute('SELECT * FROM zones ORDER BY name')]
    def zone(self,name,locations):
        if not name.strip():raise ValueError('La zona necesita un nombre.')
        with self.connect() as c:
            c.execute('INSERT OR IGNORE INTO zones(name) VALUES (?)',(name.strip(),))
            zid=c.execute('SELECT id FROM zones WHERE name=?',(name.strip(),)).fetchone()[0]
            c.execute('DELETE FROM zone_locations WHERE zone_id=?',(zid,))
            for lid in locations:c.execute('INSERT INTO zone_locations VALUES (?,?)',(zid,int(lid)))
        return self.zones()
    def remove_location(self,lid):
        with self.connect() as c:
            c.execute('DELETE FROM segments WHERE file_id IN (SELECT id FROM files WHERE location_id=?)',(lid,))
            c.execute('DELETE FROM files WHERE location_id=?',(lid,));c.execute('DELETE FROM zone_locations WHERE location_id=?',(lid,));c.execute('DELETE FROM locations WHERE id=?',(lid,))
