"""Compact native search panel: text, image and audio share one results view."""
import datetime
import os
import shutil
import signal
import subprocess
import tempfile
import threading
from pathlib import Path
import gi
gi.require_version('Gtk','4.0');gi.require_version('Adw','1')
from gi.repository import Gtk, Adw, GLib, Gio, Gdk, GdkPixbuf, Pango
from .app import label, button, human
from .readers import kind
from .progress import IndexProgress

ICONS={'text':'text-x-generic-symbolic','image':'image-x-generic-symbolic',
       'video':'video-x-generic-symbolic','audio':'audio-x-generic-symbolic',
       'other':'application-x-executable-symbolic'}
TYPES={'text':'Documento','image':'Imagen','video':'Video','audio':'Audio','other':'Archivo'}

class QuickWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title='Brújula')
        self.app=app;self.client=app.client;self.generation=0;self.snapshot={};self.scope_items=[{}]
        self.media=None;self.recorder=None;self.record_timeout=None;self.record_finishing=False;self.debounce=None
        self.temp=tempfile.TemporaryDirectory(prefix='brujula-input-');self.selected=None;self.pictures={}
        self.poll_pending=False;self.scope_signature=None;self.alive=True
        self.set_decorated(False);self.set_default_size(880,148);self.add_css_class('quick-window')
        css=Gtk.CssProvider();css.load_from_data(b'''
            .quick-window { background-color: transparent; }
            .quick-panel { background-color: @window_bg_color; border-radius: 18px; border: 1px solid alpha(@window_fg_color, .17); }
            .quick-entry { font-size: 20px; background: transparent; border: none; box-shadow: none; }
            .quick-results { background: transparent; }
            .quick-results row { border-radius: 9px; margin: 2px 4px; }
            .quick-results row:selected { background: alpha(@accent_color, .28); }
            .quick-preview { background: alpha(@window_fg_color, .035); border-radius: 12px; padding: 16px; }
            .quick-attachment { background: alpha(@accent_color, .13); border-radius: 9px; padding: 6px; }
        ''')
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(),css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        root=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8);root.add_css_class('quick-panel')
        top=Gtk.Box(spacing=4);top.set_margin_top(10);top.set_margin_start(14);top.set_margin_end(10)
        self.entry=Gtk.Entry(placeholder_text='¿Qué archivo buscas?',hexpand=True);self.entry.add_css_class('quick-entry')
        self.entry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY,'system-search-symbolic')
        self.entry.connect('changed',self.changed);self.entry.connect('activate',lambda _:self.submit());top.append(self.entry)
        top.append(button('Buscar con una imagen',lambda _:self.choose('image'),'image-x-generic-symbolic'))
        self.mic=button('Grabar una consulta de voz',lambda _:self.toggle_record(),'audio-input-microphone-symbolic');top.append(self.mic)
        top.append(button('Buscar con un archivo de audio',lambda _:self.choose('audio'),'audio-x-generic-symbolic'))
        top.append(button('Configuración y ubicaciones',lambda _:app.show_manager(),'emblem-system-symbolic'))
        top.append(button('Ocultar · Esc',lambda _:self.hide_panel(),'window-close-symbolic'));root.append(top)
        controls=Gtk.Box(spacing=8);controls.set_margin_start(18);controls.set_margin_end(18)
        self.scopes=Gtk.DropDown.new_from_strings(['Todas las ubicaciones']);self.scopes.set_tooltip_text('Dónde buscar')
        self.scopes.connect('notify::selected',lambda *_:self.submit_if_query());controls.append(self.scopes)
        self.types=Gtk.DropDown.new_from_strings(['Todos los archivos','Documentos','Imágenes','Videos','Audio'])
        self.types.connect('notify::selected',lambda *_:self.submit_if_query());controls.append(self.types)
        self.spinner=Gtk.Spinner();controls.append(self.spinner);root.append(controls)
        self.setup_box=Gtk.Box(spacing=8);self.setup_box.set_margin_start(18);self.setup_box.set_margin_end(18)
        self.setup_label=label('Preparación inicial de IA',True);self.setup_label.set_hexpand(True);self.setup_box.append(self.setup_label)
        self.setup_box.append(button('Preparar IA',lambda _:(app.show_manager(),app.manager.prepare_ai())));self.setup_box.set_visible(False);root.append(self.setup_box)
        self.attachment=Gtk.Box(spacing=8);self.attachment.add_css_class('quick-attachment');self.attachment.set_margin_start(18);self.attachment.set_margin_end(18)
        self.attachment.set_halign(Gtk.Align.START)
        self.attachment_image=Gtk.Picture();self.attachment_image.set_content_fit(Gtk.ContentFit.CONTAIN);self.attachment_image.set_can_shrink(True);self.attachment_image.set_size_request(112,84);self.attachment_image.set_visible(False);self.attachment.append(self.attachment_image)
        self.attachment_name=label('');self.attachment_name.set_hexpand(True);self.attachment.append(self.attachment_name)
        remove_attachment=button('Quitar',lambda _:self.clear_media(),'edit-clear-symbolic');remove_attachment.set_valign(Gtk.Align.START);self.attachment.append(remove_attachment);self.attachment.set_visible(False);root.append(self.attachment)
        self.content=Gtk.Box(spacing=12);self.content.set_margin_start(12);self.content.set_margin_end(12);self.content.set_visible(False)
        self.rows=Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE);self.rows.add_css_class('quick-results')
        self.rows.connect('row-selected',self.row_selected);self.rows.connect('row-activated',lambda _,row:self.open_result(row.result))
        scroll=Gtk.ScrolledWindow();scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC);scroll.set_min_content_width(320);scroll.set_size_request(335,360);scroll.set_child(self.rows);self.content.append(scroll)
        self.preview=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10,hexpand=True);self.preview.add_css_class('quick-preview')
        self.poster=Gtk.Picture();self.poster.set_content_fit(Gtk.ContentFit.CONTAIN);self.poster.set_can_shrink(True);self.poster.set_size_request(370,205);self.preview.append(self.poster)
        self.preview_title=label('');self.preview_title.add_css_class('heading');self.preview.append(self.preview_title)
        self.preview_path=label('',True);self.preview_path.set_ellipsize(Pango.EllipsizeMode.MIDDLE);self.preview_path.set_wrap(False);self.preview.append(self.preview_path)
        self.preview_meta=label('',True);self.preview.append(self.preview_meta)
        self.preview_reason=label('',True);self.preview.append(self.preview_reason)
        self.preview_excerpt=label('',True);self.preview_excerpt.set_ellipsize(Pango.EllipsizeMode.END);self.preview_excerpt.set_lines(3);self.preview.append(self.preview_excerpt)
        actions=Gtk.Box(spacing=8)
        self.open_btn=button('Abrir',lambda _:self.open_result(self.selected));self.open_btn.add_css_class('suggested-action');actions.append(self.open_btn)
        actions.append(button('Mostrar carpeta',lambda _:self.open_result(self.selected,True)))
        actions.append(button('Copiar ruta',lambda _:self.copy_path(),'edit-copy-symbolic'));self.preview.append(actions)
        self.content.append(self.preview);root.append(self.content)
        self.index_progress=IndexProgress(compact=True);self.index_progress.set_margin_start(18);self.index_progress.set_margin_end(18);root.append(self.index_progress)
        self.status=label('Texto, imagen o voz · Enter buscar · Esc ocultar',True);self.status.set_margin_start(18);self.status.set_margin_end(18);self.status.set_margin_bottom(12);root.append(self.status)
        self.toast=Adw.ToastOverlay();self.toast.set_child(root);self.set_content(self.toast)
        keys=Gtk.EventControllerKey();keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE);keys.connect('key-pressed',self.key_pressed);self.add_controller(keys)
        drop=Gtk.DropTarget.new(Gio.File,Gdk.DragAction.COPY);drop.connect('drop',self.dropped);root.add_controller(drop)
        self.connect('close-request',lambda *_:self.hide_panel())
        self.timer=GLib.timeout_add_seconds(5,self.poll);self.poll()
    def show_panel(self):
        self.present();self.entry.grab_focus();self.entry.select_region(0,-1);self.poll()
    def hide_panel(self):
        if self.recorder:self.stop_record(search=False)
        self.set_visible(False);return True
    def error(self,message):
        self.spinner.stop();self.status.set_text(message[:180]);self.toast.add_toast(Adw.Toast.new(message[:240]));return False
    def poll(self):
        if not self.alive:return False
        if not self.poll_pending and not self.client.lock.locked():
            self.poll_pending=True;self.client.async_call('status',self.received,self.poll_error)
        return True
    def poll_error(self,message):self.poll_pending=False;return self.error(message)
    def received(self,data):
        self.poll_pending=False;self.snapshot=data
        self.index_progress.update(data)
        self.setup_box.set_visible(not data.get('runtime_ready',True) or not data['model_ready'])
        setup=data.get('setup',{});message=setup.get('message','Prepara el motor y descarga el modelo por separado')
        if setup.get('phase')=='model':message+=f" · {human(data['model_bytes'])} recibidos"
        self.setup_label.set_text(message)
        theme=data['settings']['theme'];Adw.StyleManager.get_default().set_color_scheme({'system':Adw.ColorScheme.DEFAULT,'dark':Adw.ColorScheme.FORCE_DARK,'light':Adw.ColorScheme.FORCE_LIGHT}.get(theme,Adw.ColorScheme.DEFAULT))
        items=[('Todas las ubicaciones',{})]
        items += [(l['name']+(' · no incluida' if not l['enabled'] else '')+(' · desconectado' if not l['online'] else ''),{'locations':[l['id']]}) for l in data['locations']]
        items += [('Disco · '+d['name']+(' · completo' if d.get('whole') else ' · parcial' if d.get('partial') else ' · no incluido'),{'volume':d['uuid']}) for d in data['volumes']]
        items += [('Zona · '+z['name'],{'locations':z['locations']}) for z in data['zones']]
        signature=str(items)
        if signature!=self.scope_signature:
            previous=self.scope_items[self.scopes.get_selected()] if self.scopes.get_selected()<len(self.scope_items) else {}
            self.scope_signature=signature;self.scope_items=[f for _,f in items]
            self.scopes.set_model(Gtk.StringList.new([n for n,_ in items]));self.scopes.set_selected(next((i for i,f in enumerate(self.scope_items) if f==previous),0))
        if not data['locations'] and not self.entry.get_text() and not self.media:
            self.status.set_text('Añade carpetas desde ⚙ para empezar · Esc ocultar')
        return False
    def changed(self,*_):
        self.selected=None
        if self.debounce:GLib.source_remove(self.debounce)
        self.debounce=GLib.timeout_add(550,self.debounced)
    def debounced(self):
        self.debounce=None
        if len(self.entry.get_text().strip())>=2 or self.media:self.submit()
        elif not self.entry.get_text():
            self.generation+=1;self.content.set_visible(False);self.set_default_size(880,148);self.spinner.stop()
        return False
    def submit_if_query(self):
        if self.entry.get_text().strip() or self.media:self.submit()
    def submit(self):
        if self.recorder:return
        text=self.entry.get_text().strip()
        if not text and not self.media:return
        self.generation+=1;generation=self.generation;self.selected=None;self.spinner.start();self.status.set_text('Buscando… la primera consulta puede cargar el modelo')
        index=self.scopes.get_selected();filters=dict(self.scope_items[index] if index<len(self.scope_items) else {})
        filters['kind']=['','text','image','video','audio'][self.types.get_selected()]
        self.client.async_call('search',lambda r:self.show_results(r) if generation==self.generation else False,
                               lambda e:self.error(e) if generation==self.generation else False,
                               query=text,filters=filters,query_input=self.media)
    def clear_rows(self):
        child=self.rows.get_first_child()
        while child:
            following=child.get_next_sibling();self.rows.remove(child);child=following
    def show_results(self,data):
        self.spinner.stop();self.clear_rows();self.pictures={};self.selected=None
        results=data['results'][:12];self.content.set_visible(bool(results));self.set_default_size(880,540 if results else 148)
        self.status.set_text(f"{len(results)} resultados · ↑↓ elegir · Enter abrir · Esc ocultar" if results else 'Sin resultados. Prueba otra descripción o amplía el ámbito.')
        if data.get('warning'):self.status.set_text(data['warning'])
        for result in results:
            row=Gtk.ListBoxRow();row.result=result
            box=Gtk.Box(spacing=10);box.set_margin_top(8);box.set_margin_bottom(8);box.set_margin_start(8);box.set_margin_end(8)
            picture=Gtk.Picture();picture.set_size_request(46,46);picture.set_content_fit(Gtk.ContentFit.COVER);picture.set_can_shrink(True)
            picture.set_paintable(Gtk.IconTheme.get_for_display(Gdk.Display.get_default()).lookup_icon(ICONS[result['kind']],None,40,1,Gtk.TextDirection.NONE,Gtk.IconLookupFlags(0)))
            self.pictures[result['id']]=picture;box.append(picture)
            description=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=3,hexpand=True)
            title=label(result['name']);title.set_wrap(False);title.set_ellipsize(Pango.EllipsizeMode.MIDDLE);title.set_max_width_chars(29);description.append(title)
            subtitle=label(f"{TYPES[result['kind']]} · {human(result['size'])}",True);description.append(subtitle)
            place=label(result['location_name']+(' · desconectado' if not result['online'] else ''),True);description.append(place)
            box.append(description);row.set_child(box);self.rows.append(row)
        if results:self.rows.select_row(self.rows.get_row_at_index(0))
        generation=self.generation
        if results:self.client.async_call('thumbnails',lambda values:self.thumbnails_received(values,generation),None,
                         items=[{'id':r['id'],'position':r.get('match_position')} for r in results])
        return False
    def thumbnails_received(self,values,generation):
        if generation!=self.generation:return False
        for item in values:
            if item['path'] and item['id'] in self.pictures:
                self.pictures[item['id']].set_filename(item['path'])
                if self.selected and self.selected['id']==item['id']:self.poster.set_filename(item['path'])
        return False
    def row_selected(self,_,row):
        if not row:return
        result=row.result;self.selected=result
        self.poster.set_paintable(self.pictures[result['id']].get_paintable())
        self.preview_title.set_text(result['name']);self.preview_path.set_text(result['path']);self.preview_path.set_tooltip_text(result['path'])
        date=datetime.datetime.fromtimestamp(result['mtime_ns']/1e9).strftime('%d/%m/%Y')
        self.preview_meta.set_text(f"{TYPES[result['kind']]} · {human(result['size'])} · {date}")
        reason='Coincidencia por '+result['reason'].lower()
        pos=result.get('match_position')
        if pos is not None:reason+=f" · muestra en {int(pos)//60}:{int(pos)%60:02d}"
        self.preview_reason.set_text(reason)
        self.preview_excerpt.set_text((result.get('excerpt') or '')[:340]);self.open_btn.set_sensitive(bool(result['online']))
    def open_result(self,result,folder=False):
        if not result:return
        path=Path(result['path'])
        if not path.exists():return self.error('Conecta el disco para abrir este archivo.')
        try:
            Gio.AppInfo.launch_default_for_uri((path.parent if folder else path).as_uri(),None)
            if not folder:self.client.async_call('opened',id=result['id'])
        except Exception as exc:self.error(str(exc))
    def copy_path(self):
        if self.selected:Gdk.Display.get_default().get_clipboard().set(self.selected['path'])
    def key_pressed(self,_,key,keycode,modifiers):
        if key==Gdk.KEY_Escape:self.hide_panel();return True
        if key in (Gdk.KEY_Down,Gdk.KEY_Up):
            current=self.rows.get_selected_row();index=current.get_index() if current else -1
            row=self.rows.get_row_at_index(max(0,index+(1 if key==Gdk.KEY_Down else -1)))
            if row:self.rows.select_row(row)
            return True
        if key in (Gdk.KEY_Return,Gdk.KEY_KP_Enter) and self.selected and not self.spinner.get_spinning():
            if modifiers&Gdk.ModifierType.CONTROL_MASK:self.open_result(self.selected,True)
            else:self.open_result(self.selected)
            return True
        if key==Gdk.KEY_v and modifiers&Gdk.ModifierType.CONTROL_MASK:
            clipboard=Gdk.Display.get_default().get_clipboard()
            if clipboard.get_formats().contain_gtype(Gdk.Texture):
                clipboard.read_texture_async(None,self.paste_texture);return True
        return False
    def paste_texture(self,clipboard,result):
        try:
            texture=clipboard.read_texture_finish(result);path=Path(self.temp.name)/'clipboard.png'
            texture.save_to_png(str(path));self.set_media(path,'image')
        except Exception as exc:self.error(str(exc))
    def choose(self,modality):
        chooser=Gtk.FileChooserNative.new('Imagen de referencia' if modality=='image' else 'Audio de referencia',self,Gtk.FileChooserAction.OPEN,'Buscar','Cancelar')
        f=Gtk.FileFilter();f.set_name('Imágenes' if modality=='image' else 'Audio');f.add_mime_type('image/*' if modality=='image' else 'audio/*');chooser.add_filter(f)
        def chosen(dialog,response):
            if response==Gtk.ResponseType.ACCEPT:self.set_media(dialog.get_file().get_path(),modality)
            dialog.destroy()
        chooser.connect('response',chosen);chooser.show()
    def dropped(self,_,file,x,y):
        path=file.get_path();category=kind(path) if path else ''
        if category not in ('image','audio'):self.error('Arrastra una imagen o un archivo de audio.');return False
        self.set_media(path,category);return True
    def set_media(self,path,modality):
        if modality=='image':
            try:
                pixbuf=GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path),112,84,True).apply_embedded_orientation()
                self.attachment_image.set_paintable(Gdk.Texture.new_for_pixbuf(pixbuf))
            except GLib.Error as exc:
                return self.error('No se pudo mostrar la imagen: '+str(exc))
        self.media={'modality':modality,'path':str(path)}
        self.attachment_image.set_visible(modality=='image')
        self.attachment_name.set_visible(modality!='image')
        self.attachment_name.set_text('Audio · '+Path(path).name if modality=='audio' else '')
        self.attachment.set_visible(True);self.submit()
    def clear_media(self):
        self.media=None;self.attachment_image.set_paintable(None);self.attachment.set_visible(False)
        if self.entry.get_text().strip():self.submit()
        else:self.generation+=1;self.content.set_visible(False);self.set_default_size(880,148)
    def toggle_record(self):
        if self.record_finishing:return
        if self.recorder:self.stop_record();return
        command=shutil.which('pw-record') or shutil.which('arecord')
        if not command:return self.error('No hay grabador disponible. Puedes adjuntar un archivo de audio.')
        self.record_path=Path(self.temp.name)/'voz.wav';self.record_log=(Path(self.temp.name)/'record.log').open('w')
        args=[command,'--rate=16000','--channels=1','--format=s16',str(self.record_path)] if Path(command).name=='pw-record' else [command,'-q','-r','16000','-c','1','-f','S16_LE',str(self.record_path)]
        self.recorder=subprocess.Popen(args,stdout=subprocess.DEVNULL,stderr=self.record_log)
        self.mic.set_icon_name('media-playback-stop-symbolic');self.mic.set_tooltip_text('Terminar grabación y buscar')
        self.status.set_text('Grabando voz… pulsa ■ para buscar · máximo 30 segundos')
        self.record_timeout=GLib.timeout_add_seconds(30,lambda:self.stop_record())
        GLib.timeout_add(500,self.check_record)
    def check_record(self):
        if not self.recorder:return False
        if self.recorder.poll() is not None:
            self.stop_record(search=False);self.error('No se pudo grabar. Revisa el micrófono predeterminado de Zorin.');return False
        return True
    def stop_record(self,search=True):
        if self.record_timeout:GLib.source_remove(self.record_timeout);self.record_timeout=None
        process=self.recorder
        if not process:return False
        self.record_finishing=True;self.recorder=None;record_log=self.record_log;record_path=self.record_path;self.mic.set_icon_name('audio-input-microphone-symbolic');self.mic.set_tooltip_text('Grabar una consulta de voz')
        def finish():
            if process.poll() is None:process.send_signal(signal.SIGINT)
            try:process.wait(timeout=3)
            except subprocess.TimeoutExpired:process.kill();process.wait()
            record_log.close();self.record_finishing=False
            if search:
                if record_path.exists() and record_path.stat().st_size>100:GLib.idle_add(self.set_media,record_path,'audio')
                else:GLib.idle_add(self.error,'No se pudo grabar. Comprueba el micrófono predeterminado de Zorin.')
        threading.Thread(target=finish,daemon=True).start();return False
    def dispose(self):
        self.alive=False
        self.index_progress.close()
        if self.recorder:self.stop_record(search=False)
        if self.debounce:GLib.source_remove(self.debounce)
        if self.timer:GLib.source_remove(self.timer)
        self.temp.cleanup()
