"""GTK desktop client. Runs under system Python; ML lives in the project venv."""
import datetime, json, os, subprocess, threading, signal
from pathlib import Path
# The application indexes local files; use GIO's direct local backend.
os.environ.setdefault('GIO_USE_VFS','local')
import gi
gi.require_version('Gtk','4.0');gi.require_version('Adw','1')
from gi.repository import Gtk, Adw, GLib, Gio, Gdk, Pango
from .progress import IndexProgress
ROOT=Path(__file__).resolve().parents[1]
KIND={'':'Todos los tipos','text':'Documentos','image':'Imágenes','video':'Videos','audio':'Audio','other':'Otros'}
def human(n):
    for unit in ['B','KB','MB','GB','TB']:
        if n<1000:return f'{n:.1f} {unit}'
        n/=1000
    return f'{n:.1f} PB'
def label(text,dim=False):
    l=Gtk.Label(label=text,xalign=0,wrap=True)
    if dim:l.add_css_class('dim-label')
    return l

def button(text,callback,icon=None):
    b=Gtk.Button(label=text)
    if icon:b.set_icon_name(icon);b.set_tooltip_text(text)
    b.connect('clicked',callback);return b

class Client:
    def __init__(self):
        logs=Path.home()/'.local/share/brujula';logs.mkdir(parents=True,exist_ok=True)
        self.log=(logs/'backend.log').open('a')
        self.p=subprocess.Popen([str(ROOT/'.venv/bin/python'),'-m','embedding_app.backend','--rpc'],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,text=True,bufsize=1)
        self.lock=threading.Lock()
    def call(self,op,**kw):
        with self.lock:
            self.p.stdin.write(json.dumps({'op':op,**kw})+'\n');self.p.stdin.flush()
            response=self.p.stdout.readline()
            if not response:raise RuntimeError('El motor se cerró. Consulta ~/.local/share/brujula/backend.log')
            result=json.loads(response)
            if 'error' in result:raise RuntimeError(result['error'])
            return result['result']
    def async_call(self,op,callback=None,error=None,**kw):
        def work():
            try:
                result=self.call(op,**kw)
                if callback:GLib.idle_add(callback,result)
            except Exception as exc:
                if error:GLib.idle_add(error,str(exc))
        threading.Thread(target=work,daemon=True).start()
    def close(self):
        def work():
            try:self.call('shutdown');self.p.wait(timeout=30)
            except Exception:self.p.terminate()
            self.log.close()
        threading.Thread(target=work,daemon=True).start()

class Window(Adw.ApplicationWindow):
    def __init__(self,app,client=None):
        super().__init__(application=app,title='Brújula · Tus archivos por significado')
        self.set_default_size(1120,760);self.owns_client=client is None;self.client=client or Client();self.snapshot={};self.scope=None;self.scope_volume=None;self.generation=0;self.scope_signature=None;self.poll_pending=False
        outer=Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        header=Adw.HeaderBar();header.pack_start(button('Añadir carpeta',lambda _:self.add_folder(), 'folder-new-symbolic'))
        header.pack_end(button('Configuración',lambda _:self.settings(), 'emblem-system-symbolic'))
        header.pack_start(button('Buscador rápido',lambda _:app.do_activate(),'system-search-symbolic'))
        header.pack_end(button('Salir de Brújula',lambda _:app.quit(),'application-exit-symbolic'))
        header.pack_end(button('Actividad',lambda _:self.activity(), 'view-list-symbolic'))
        outer.append(header)
        body=Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL);body.set_position(230);body.set_vexpand(True)
        self.sidebar=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8)
        for setter in ['set_margin_top','set_margin_bottom','set_margin_start','set_margin_end']:getattr(self.sidebar,setter)(16)
        side_scroll=Gtk.ScrolledWindow();side_scroll.set_child(self.sidebar);side_scroll.set_min_content_width(215);body.set_start_child(side_scroll)
        main=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12)
        for setter in ['set_margin_top','set_margin_bottom','set_margin_start','set_margin_end']:getattr(main,setter)(20)
        title=label('Encuentra lo que recuerdas');title.add_css_class('title-1');main.append(title)
        self.entry=Gtk.SearchEntry(placeholder_text='Por ejemplo: videos sobre instalar Linux');self.entry.set_hexpand(True)
        self.entry.connect('activate',lambda _:self.search());main.append(self.entry)
        self.scope_label=label('Buscar en: Todas las ubicaciones',True);main.append(self.scope_label)
        toolbar=Gtk.Box(spacing=8)
        self.kind=Gtk.DropDown.new_from_strings(list(KIND.values()));self.kind.connect('notify::selected',lambda *_:self.search());toolbar.append(self.kind)
        self.sort=Gtk.DropDown.new_from_strings(['Relevancia','Más grandes','Más recientes','Más abiertos aquí']);self.sort.connect('notify::selected',lambda *_:self.search());toolbar.append(self.sort)
        self.stars=Gtk.CheckButton(label='Importantes');self.stars.connect('toggled',lambda _:self.search());toolbar.append(self.stars)
        self.offline=Gtk.CheckButton(label='Incluir desconectados',active=True);self.offline.connect('toggled',lambda _:self.search());toolbar.append(self.offline)
        main.append(toolbar)
        filters=Gtk.Box(spacing=8)
        self.minimum=Gtk.SpinButton.new_with_range(0,100000,0.1);self.minimum.set_digits(1);self.minimum.set_tooltip_text('Tamaño mínimo en GB; 0 sin límite')
        filters.append(label('Mín. GB'));filters.append(self.minimum)
        self.maximum=Gtk.SpinButton.new_with_range(0,100000,0.1);self.maximum.set_digits(1);self.maximum.set_tooltip_text('Tamaño máximo en GB; 0 sin límite');filters.append(label('Máx. GB'));filters.append(self.maximum)
        self.age=Gtk.DropDown.new_from_strings(['Cualquier fecha','Modificado en 7 días','Modificado en 30 días','Modificado en 365 días']);filters.append(self.age)
        filters.append(button('Aplicar',lambda _:self.search()));main.append(filters)
        self.folder=Gtk.Entry(placeholder_text='Limitar a una carpeta indexada (ruta opcional)');self.folder.connect('activate',lambda _:self.search());main.append(self.folder)
        self.summary=label('Añade una carpeta para comenzar. Solo se analizarán las ubicaciones que elijas.',True);main.append(self.summary)
        self.results=Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE);self.results.add_css_class('boxed-list')
        scroll=Gtk.ScrolledWindow(vexpand=True);scroll.set_child(self.results);main.append(scroll);body.set_end_child(main);outer.append(body)
        self.index_progress=IndexProgress();self.index_progress.set_margin_start(16);self.index_progress.set_margin_end(16);self.index_progress.set_margin_top(8);outer.append(self.index_progress)
        footer=Gtk.Box(spacing=10);footer.set_margin_start(16);footer.set_margin_end(16);footer.set_margin_top(10);footer.set_margin_bottom(10)
        self.status_label=label('Preparando…',True);self.status_label.set_hexpand(True);self.status_label.set_ellipsize(Pango.EllipsizeMode.END);self.status_label.set_wrap(False);footer.append(self.status_label)
        footer.append(button('Actualizar',lambda _:self.command('start')))
        self.pause_btn=button('Pausar',lambda _:self.command('start' if self.snapshot.get('paused') else 'pause'));footer.append(self.pause_btn)
        footer.append(button('Detener',lambda _:self.command('stop')));outer.append(footer)
        self.toast=Adw.ToastOverlay();self.toast.set_child(outer);self.set_content(self.toast)
        self.connect('close-request',self.close);self.alive=True;self.timer=GLib.timeout_add_seconds(3,self.poll);self.poll()
    def error(self,text):self.toast.add_toast(Adw.Toast.new(text[:250]));return False
    def command(self,op,**kw):self.client.async_call(op,lambda _:self.poll(),self.error,**kw)
    def poll(self):
        if not self.alive:return False
        if not self.poll_pending and not self.client.lock.locked():
            self.poll_pending=True;self.client.async_call('status',self.received,self.poll_error)
        return True
    def poll_error(self,error):self.poll_pending=False;return self.error(error)
    def received(self,data):
        self.poll_pending=False;first=not self.snapshot;previous=self.snapshot;self.snapshot=data
        self.index_progress.update(data)
        state=data['index'];counts=data['counts'];model='Modelo listo' if data['model_ready'] else f"Descargando modelo: {human(data['model_bytes'])} recibidos"
        pause=' · Pausado' if data['paused'] else ''
        self.status_label.set_text(f"{state['phase']}{pause} · {state['done']}/{state['total']} · {data['files']} archivos · {model}")
        self.status_label.set_tooltip_text(state['phase'] + ('\n' + state['current'] if state.get('current') else ''))
        self.pause_btn.set_label('Continuar' if data['paused'] else 'Pausar')
        signature=json.dumps([data['locations'],data['zones'],data['volumes']],sort_keys=True)
        if signature!=self.scope_signature:self.scope_signature=signature;self.rebuild_sidebar()
        theme=data['settings']['theme'];Adw.StyleManager.get_default().set_color_scheme({'system':Adw.ColorScheme.DEFAULT,'dark':Adw.ColorScheme.FORCE_DARK,'light':Adw.ColorScheme.FORCE_LIGHT}.get(theme,Adw.ColorScheme.DEFAULT))
        if first or (not data['index']['running'] and (previous.get('files')!=data['files'] or previous.get('model_ready')!=data['model_ready'] or previous.get('index',{}).get('running'))):self.search()
        return False
    def clear(self,widget):
        child=widget.get_first_child()
        while child:
            nxt=child.get_next_sibling();widget.remove(child);child=nxt
    def rebuild_sidebar(self):
        self.clear(self.sidebar)
        self.sidebar.append(label('UBICACIONES',True));self.sidebar.append(button('Todas',lambda _:self.set_scope(None,None,'Todas las ubicaciones')))
        if not self.snapshot['locations']:self.sidebar.append(label('Ninguna carpeta incluida',True))
        for loc in self.snapshot['locations']:
            text=loc['name']+(' · no incluida' if not loc['enabled'] else '')+(' · desconectado' if not loc['online'] else '')
            row=Gtk.Box(spacing=6);toggle=Gtk.CheckButton(active=bool(loc['enabled']));toggle.set_tooltip_text('Incluir esta ubicación en búsquedas y análisis')
            toggle.connect('toggled',lambda check,loc=loc:self.set_inclusion('set_location',check,id=loc['id']))
            row.append(toggle);item=button(text,lambda _,loc=loc:self.set_scope([loc['id']],None,loc['name']));item.set_hexpand(True);row.append(item);self.sidebar.append(row)
        self.sidebar.append(button('＋ Añadir carpeta',lambda _:self.add_folder()))
        self.sidebar.append(label('DISCOS',True))
        self.sidebar.append(label('Marcar incluye el disco completo',True))
        for disk in self.snapshot['volumes']:
            row=Gtk.Box(spacing=6);toggle=Gtk.CheckButton(active=disk.get('whole',False));toggle.set_inconsistent(disk.get('partial',False))
            toggle.set_tooltip_text('Incluir todo el disco; desmarcar excluye sus ubicaciones sin borrar archivos')
            toggle.connect('toggled',lambda check,disk=disk:self.set_inclusion('set_disk',check,volume=disk['uuid']))
            row.append(toggle);column=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=2,hexpand=True)
            item=button(disk['name'],lambda _,disk=disk:self.set_scope(None,disk['uuid'],disk['name']));column.append(item)
            state='Incluido completo' if disk.get('whole') else f"Parcial · {disk.get('location_count',0)} ubicaciones" if disk.get('partial') else 'No incluido'
            if not disk.get('online',True):state+=' · desconectado'
            column.append(label(state,True));row.append(column);self.sidebar.append(row)
        self.sidebar.append(label('ZONAS',True))
        for zone in self.snapshot['zones']:
            self.sidebar.append(button(zone['name'],lambda _,zone=zone:self.set_scope(zone['locations'],None,zone['name'])))
        self.sidebar.append(button('＋ Crear zona',lambda _:self.zone_dialog()))
        self.sidebar.append(button('Gestionar ubicaciones',lambda _:self.manage_locations()))
    def set_inclusion(self,op,check,**kw):
        check.set_sensitive(False);check.set_inconsistent(False)
        def applied(_):self.scope_signature=None;self.poll();self.search();return False
        def failed(message):self.scope_signature=None;self.poll();return self.error(message)
        self.client.async_call(op,applied,failed,enabled=check.get_active(),**kw)
    def set_scope(self,lids,volume,name):
        self.scope=lids;self.scope_volume=volume;self.scope_label.set_text('Buscar en: '+name);self.search()
    def search(self):
        self.generation+=1;generation=self.generation
        filters={'locations':self.scope,'volume':self.scope_volume,'kind':list(KIND)[self.kind.get_selected()],'sort':['relevance','size','date','usage'][self.sort.get_selected()],'important':self.stars.get_active(),'offline':self.offline.get_active(),'folder':self.folder.get_text().strip()}
        if self.minimum.get_value():filters['min_size']=int(self.minimum.get_value()*1e9)
        if self.maximum.get_value():filters['max_size']=int(self.maximum.get_value()*1e9)
        days=[0,7,30,365][self.age.get_selected()]
        if days:filters['after']=__import__('time').time()-days*86400
        self.summary.set_text('Buscando… (la primera consulta puede cargar el modelo)')
        self.client.async_call('search',lambda r:self.show_results(r) if generation==self.generation else False,self.error,query=self.entry.get_text(),filters=filters)
    def show_results(self,data):
        self.clear(self.results)
        self.summary.set_text(f"{len(data['results'])} resultados mostrados · {data['mode']}"+(' · '+data['warning'] if data['warning'] else ''))
        if not data['results']:
            box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12);box.set_margin_top(30);box.set_margin_bottom(30)
            box.append(label('Sin resultados'));box.append(label('Añade una ubicación, actualiza el índice o amplía los filtros.',True));self.results.append(box)
        for r in data['results']:
            row=Gtk.Box(spacing=12);row.set_margin_top(12);row.set_margin_bottom(12);row.set_margin_start(12);row.set_margin_end(12)
            icons={'text':'text-x-generic-symbolic','image':'image-x-generic-symbolic','video':'video-x-generic-symbolic','audio':'audio-x-generic-symbolic','other':'application-x-executable-symbolic'}
            image=Gtk.Image.new_from_icon_name(icons[r['kind']]);image.set_pixel_size(32);row.append(image)
            info=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=4,hexpand=True)
            name=label(r['name']);name.add_css_class('heading');info.append(name)
            date=datetime.datetime.fromtimestamp(r['mtime_ns']/1e9).strftime('%d/%m/%Y')
            info.append(label(f"{human(r['size'])} · {date} · {r['location_name']} · {r['reason']}"+(' · Disco desconectado' if not r['online'] else ''),True))
            path=label(r['path'],True);path.set_ellipsize(Pango.EllipsizeMode.MIDDLE);path.set_wrap(False);info.append(path);row.append(info)
            star=button('Marcar importante',lambda _,r=r:self.toggle_star(r),'starred-symbolic' if r['important'] else 'non-starred-symbolic');row.append(star)
            row.append(button('Detalles',lambda _,r=r:self.details(r),'dialog-information-symbolic'))
            open_btn=button('Abrir',lambda _,r=r:self.open_file(r));open_btn.set_sensitive(bool(r['online']));row.append(open_btn);self.results.append(row)
        return False
    def toggle_star(self,r):self.client.async_call('important',lambda _:self.search(),self.error,id=r['id'],value=not r['important'])
    def open_file(self,r,folder=False):
        path=Path(r['path'])
        if not path.exists():return self.error('Archivo no disponible. Conecta el disco y actualiza el índice.')
        try:
            Gio.AppInfo.launch_default_for_uri((path.parent if folder else path).as_uri(),None)
            if not folder:self.command('opened',id=r['id'])
        except Exception as exc:self.error(str(exc))
    def dialog(self,title,width=600):
        win=Adw.Window(title=title,transient_for=self,modal=True);win.set_default_size(width,500)
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12)
        for setter in ['set_margin_top','set_margin_bottom','set_margin_start','set_margin_end']:getattr(box,setter)(20)
        heading=label(title);heading.add_css_class('title-2');box.append(heading)
        scroll=Gtk.ScrolledWindow(vexpand=True);scroll.set_child(box);win.set_content(scroll);return win,box
    def details(self,r):
        win,box=self.dialog(r['name'])
        for text in [r['path'],f"Tamaño lógico: {human(r['size'])}",f"Estado: {r['status']}",f"Creación: {datetime.datetime.fromtimestamp(r['btime']).isoformat() if r['btime'] else 'No disponible en este sistema de archivos'}",f"Aperturas desde Brújula: {r['opens']} (no incluye otras aplicaciones)",r['error'] or '']:
            if text:box.append(label(text))
        if r['excerpt']:box.append(label('Muestra de texto (no es un resumen generado):'));box.append(label(r['excerpt'][:2000],True))
        box.append(button('Mostrar carpeta',lambda _:self.open_file(r,True)))
        box.append(button('Copiar ruta',lambda _:Gdk.Display.get_default().get_clipboard().set(r['path'])))
        box.append(button('Cerrar',lambda _:win.close()));win.present()
    def add_folder(self):
        win,box=self.dialog('Añadir una carpeta',650)
        box.append(label('Solo se analizan las carpetas o discos que incluyas.'))
        entry=Gtk.Entry(placeholder_text='Ruta de carpeta, por ejemplo ~/Downloads');box.append(entry)
        def add(path):
            if not path:return self.error('Escribe o selecciona una carpeta.')
            self.client.async_call('add_location',lambda _: (win.close(),self.poll()) and False,self.error,path=path)
        box.append(button('Añadir esta ruta',lambda _:add(entry.get_text().strip())))
        def downloads(_):
            try:path=subprocess.check_output(['xdg-user-dir','DOWNLOAD'],text=True,timeout=3).strip()
            except (OSError,subprocess.SubprocessError):path=str(Path.home()/'Downloads')
            add(path)
        box.append(button('Añadir Descargas',downloads))
        def browse(_):
            chooser=Gtk.FileChooserDialog(title='Seleccionar carpeta',transient_for=win,modal=True,action=Gtk.FileChooserAction.SELECT_FOLDER)
            chooser.add_buttons('Cancelar',Gtk.ResponseType.CANCEL,'Seleccionar',Gtk.ResponseType.ACCEPT)
            self.folder_chooser=chooser
            try:chooser.set_current_folder(Gio.File.new_for_path(str(Path.home())))
            except GLib.Error:pass
            def selected(dialog,response):
                file=dialog.get_file()
                if response==Gtk.ResponseType.ACCEPT and file and file.get_path():entry.set_text(file.get_path())
                dialog.destroy();self.folder_chooser=None
            chooser.connect('response',selected);chooser.present()
        box.append(button('Examinar carpetas…',browse));box.append(button('Cancelar',lambda _:win.close()));win.present()
    def zone_dialog(self,existing=None):
        win,box=self.dialog('Crear o actualizar zona')
        name=Gtk.Entry(placeholder_text='Nombre de la zona');box.append(name)
        choices=[]
        for loc in self.snapshot.get('locations',[]):
            check=Gtk.CheckButton(label=loc['name']);box.append(check);choices.append((loc['id'],check))
        box.append(label('Usar el nombre de una zona existente reemplaza sus ubicaciones.',True))
        def save(_):
            self.client.async_call('zone',lambda _: (win.close(),self.poll()) and False,self.error,name=name.get_text(),locations=[lid for lid,c in choices if c.get_active()])
        box.append(button('Guardar zona',save));box.append(button('Cancelar',lambda _:win.close()));win.present()
    def manage_locations(self):
        win,box=self.dialog('Ubicaciones y zonas')
        box.append(label('Quitar una ubicación elimina su índice; tus archivos permanecen intactos. Detén la indexación antes.',True))
        for loc in self.snapshot.get('locations',[]):
            line=Gtk.Box(spacing=8);l=label(loc['path']);l.set_hexpand(True);line.append(l)
            line.append(button('Quitar',lambda _,loc=loc:self.client.async_call('remove_location',lambda _: (win.close(),self.poll()) and False,self.error,id=loc['id'])));box.append(line)
        for z in self.snapshot.get('zones',[]):box.append(button('Quitar zona '+z['name'],lambda _,z=z:self.client.async_call('remove_zone',lambda _: (win.close(),self.poll()) and False,self.error,id=z['id'])))
        box.append(button('Cerrar',lambda _:win.close()));win.present()
    def settings(self):
        s=self.snapshot.get('settings',{});win,box=self.dialog('Configuración')
        controls={}
        def dropdown(key,title,values,labels=None):
            row=Gtk.Box(spacing=10);l=label(title);l.set_hexpand(True);row.append(l)
            d=Gtk.DropDown.new_from_strings(labels or [str(v) for v in values]);d.set_selected(values.index(s.get(key,values[0])));row.append(d);box.append(row);controls[key]=(d,values)
        dropdown('profile','Perfil',['Ligero','Equilibrado','Personalizado'])
        dropdown('device','Procesamiento',['auto','cpu','cuda'],['Automático','CPU','GPU NVIDIA'])
        dropdown('dimensions','Dimensiones',[128,256,512,768]);dropdown('theme','Tema',['system','light','dark'],['Sistema','Claro','Oscuro'])
        spins={}
        for key,title,lo,hi in [('video_frames','Fotogramas por video',1,48),('audio_windows','Muestras de audio',1,12),('audio_seconds','Segundos por muestra',5,30),('text_words','Palabras seleccionadas',300,6000),('scan_minutes','Revisar cambios cada (min)',1,1440),('idle_seconds','Liberar modelo tras (seg)',15,1800),('gpu_check_seconds','Comprobar GPU cada (seg)',10,3600),('gpu_max_utilization','Uso GPU máximo para indexar (%)',0,100),('gpu_min_free_mb','Memoria GPU mínima (MiB)',256,100000)]:
            row=Gtk.Box(spacing=10);l=label(title);l.set_hexpand(True);row.append(l);spin=Gtk.SpinButton.new_with_range(lo,hi,1);spin.set_value(s.get(key,lo));row.append(spin);box.append(row);spins[key]=spin
        gpu_idle=Gtk.CheckButton(label='Indexar solo cuando la GPU esté libre',active=s.get('gpu_idle_only',True));box.append(gpu_idle)
        box.append(label('La búsqueda interactiva no espera. CPU ignora esta condición. Si otra tarea empieza, se comprueba entre muestras; una operación ya iniciada termina.',True))
        audio=Gtk.CheckButton(label='Analizar audio de videos y grabaciones',active=s.get('enable_audio',True));box.append(audio)
        types={}
        for kind_,title in list(KIND.items())[1:]:
            check=Gtk.CheckButton(label='Indexar '+title.lower(),active=kind_ in s.get('types',[]));types[kind_]=check;box.append(check)
        excludes=Gtk.Entry(text=', '.join(s.get('exclude',[])),placeholder_text='Nombres de carpetas excluidas, separados por coma');box.append(label('Carpetas excluidas (nombre exacto):'));box.append(excludes)
        box.append(label('Ligero y Equilibrado aplican sus límites al guardar. Para usar los valores individuales elige Personalizado. Los cambios de análisis se aplican al actualizar el índice.',True))
        def save(_):
            values={k:options[d.get_selected()] for k,(d,options) in controls.items()};values.update({k:int(d.get_value()) for k,d in spins.items()})
            if values['profile']=='Ligero':values.update(video_frames=12,audio_windows=4,audio_seconds=20,text_words=3000)
            elif values['profile']=='Equilibrado':values.update(video_frames=24,audio_windows=8,audio_seconds=30,text_words=5000)
            values.update(gpu_idle_only=gpu_idle.get_active(),enable_audio=audio.get_active(),types=[k for k,c in types.items() if c.get_active()],exclude=[v.strip() for v in excludes.get_text().split(',') if v.strip()])
            self.client.async_call('settings',lambda _: (win.close(),self.poll()) and False,self.error,values=values)
        box.append(button('Guardar',save));box.append(button('Cancelar',lambda _:win.close()));win.present()
    def activity(self):
        win,box=self.dialog('Actividad del índice')
        data=self.snapshot;box.append(label(f"{data.get('files',0)} archivos · {human(data.get('bytes',0))} de archivos indexados"));box.append(label(str(data.get('counts',{}))))
        box.append(label('Este total corresponde a los archivos admitidos del índice; no al uso completo del disco.',True))
        for event in data.get('events',[]):box.append(label(datetime.datetime.fromtimestamp(event['time']).strftime('%H:%M')+' · '+event['message'],True))
        box.append(button('Reintentar errores',lambda _:self.command('retry')));box.append(button('Cerrar',lambda _:win.close()));win.present()
    def close(self,*_):
        self.alive=False
        self.index_progress.close()
        GLib.source_remove(self.timer)
        if self.owns_client:self.client.close()
        else:self.get_application().manager=None
        return False

class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id='local.brujula.search',flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.client=None;self.quick=None;self.manager=None
    def do_startup(self):
        Adw.Application.do_startup(self)
        self.client=Client();self.hold()
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT,signal.SIGTERM,lambda:self.quit() or False)
        self.connect('shutdown',self.cleanup)
    def do_activate(self):
        from .quick import QuickWindow
        if self.quick is None:self.quick=QuickWindow(self)
        if self.manager:self.manager.set_visible(False)
        self.quick.show_panel()
    def show_manager(self):
        if self.quick:self.quick.hide_panel()
        if self.manager is None:self.manager=Window(self,self.client)
        self.manager.present()
    def cleanup(self,*_):
        if self.quick:self.quick.dispose()
        if self.client:self.client.close()
if __name__=='__main__':App().run(None)
