"""Visual QA with explicitly synthetic results, isolated from the personal index."""
import os,sys,subprocess,re
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
os.environ['BRUJULA_DATA']=str(root/'work/popup-data')
from embedding_app.storage import Store
from embedding_app.volumes import add_location
from embedding_app.indexer import Indexer
from embedding_app.app import App
from gi.repository import GLib,Gdk
store=Store();store.update_settings({'theme':'dark'})
add_location(store,root/'work/popup-assets','Ejemplos')
class NullEncoder:
    def close(self):pass
Indexer(store,NullEncoder()).scan(store.settings())
with store.connect() as c:
    rows=[dict(r)|{'location_name':'Ejemplos','online':1,'reason':'Imagen' if r['kind']!='text' else 'Texto','match_position':.5 if r['kind']=='video' else None} for r in c.execute('SELECT * FROM files ORDER BY CASE kind WHEN "video" THEN 0 WHEN "image" THEN 1 ELSE 2 END')]
app=App();errors=[]
def setup():
    try:
        q=app.quick
        q.entry.set_text('vacaciones en las montañas')
        if q.debounce:GLib.source_remove(q.debounce);q.debounce=None
        q.show_results({'results':rows,'mode':'Demostración','warning':''})
        q.status.set_text('3 resultados de demostración · ↑↓ elegir · Enter abrir · Esc ocultar')
        GLib.timeout_add_seconds(4,capture)
    except Exception as exc:errors.append(str(exc));app.quit()
    return False
def capture():
    try:
        tree=subprocess.check_output(['xwininfo','-root','-tree'],text=True)
        match=re.search(r'(0x[0-9a-fA-F]+) "Brújula"',tree)
        subprocess.run(['import','-window',match.group(1) if match else 'root',str(root/'work/quick-panel.png')],check=True)
        q=app.quick;assert q.selected['kind']=='video'
        assert q.key_pressed(None,Gdk.KEY_Down,0,Gdk.ModifierType(0));assert q.selected['kind']=='image'
        q.hide_panel();assert not q.get_visible();q.show_panel();assert q.get_visible()
        app.show_manager();assert app.manager.client is q.client
        print('QUICK_PANEL_OK',flush=True)
    except Exception as exc:errors.append(str(exc));__import__('traceback').print_exc()
    app.quit();return False
app.connect('activate',lambda *_:GLib.timeout_add_seconds(2,setup))
app.run(None)
if errors:raise SystemExit(1)
