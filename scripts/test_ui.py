"""Exercise GTK callbacks/dialogs without reading the user's files."""
import os,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
os.environ['BRUJULA_DATA']=str(root/'work/ui-integration-data')
from embedding_app.app import App,Window
from gi.repository import GLib
app=App();errors=[]
def run():
    try:
        w=app.manager
        assert w.snapshot,'Backend did not respond'
        f={'id':1,'name':'Ejemplo.pdf','path':'/tmp/ejemplo.pdf','size':12500000,'mtime_ns':1700000000000000000,'location_name':'Documentos','reason':'Texto','kind':'text','online':0,'important':0,'status':'pending','error':'','btime':None,'opens':0,'excerpt':'Documento sintético de ejemplo.'}
        w.show_results({'results':[f],'mode':'Prueba visual','warning':''})
        w.details(f);w.settings();w.zone_dialog();w.manage_locations();w.activity()
        print('GTK_CALLBACKS_OK',flush=True)
    except Exception as exc:
        errors.append(str(exc));__import__('traceback').print_exc()
    GLib.timeout_add_seconds(1,finish);return False
def finish():
    for w in list(app.get_windows()):w.close()
    app.quit();return False
app.connect('activate',lambda *_:(app.show_manager(),GLib.timeout_add_seconds(3,run)))
app.run(None)
if errors:raise SystemExit(1)
