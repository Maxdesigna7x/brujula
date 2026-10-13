"""Shared GTK indexing progress; discovery never displays a guessed percentage."""
import gi
gi.require_version('Gtk','4.0')
from gi.repository import Gtk, GLib, Pango

class IndexProgress(Gtk.Box):
    def __init__(self,compact=False):
        super().__init__(orientation=Gtk.Orientation.VERTICAL,spacing=4)
        self.compact=compact;self.was_running=False;self.pulsing=False;self.timer=None
        self.bar=Gtk.ProgressBar(show_text=True);self.bar.set_pulse_step(.06);self.append(self.bar)
        self.detail=Gtk.Label(xalign=0);self.detail.add_css_class('dim-label');self.detail.set_ellipsize(Pango.EllipsizeMode.MIDDLE);self.append(self.detail)
        if compact:self.set_visible(False)
    def update(self,data):
        state=data['index'];running=state['running'];paused=data.get('paused',False)
        total=state.get('total',0);done=state.get('done',0);phase=state['phase'];stage=state.get('stage','')
        finished=self.was_running and not running and stage=='complete'
        self.set_visible(not self.compact or running or (paused and stage!='idle') or finished)
        self.was_running=running
        known=stage not in ('scan','metadata','waiting_model') and total>0
        if known:
            parts=state.get('part_total',0)
            fraction=(done+(min(state.get('part_done',0),parts)/parts if parts else 0))/total
            fraction=min(1,max(0,fraction));self.bar.set_fraction(fraction)
            text=f'{done}/{total} archivos · {fraction:.0%}'
            if stage=='complete':text=f'Revisión completada · {done}/{total} archivos'
            if stage=='stopped':text='Detenido · '+text
            elif paused:text='Pausado · '+text
            elif phase.startswith('Esperando GPU'):text='Esperando GPU libre · '+text
        else:
            self.bar.set_fraction(1 if stage=='complete' else 0);text=phase
            if stage=='scan':text=f"Revisando archivos · {state.get('scanned',0)} encontrados"
            if paused:text='Pausado · '+text
        self.bar.set_text(text)
        location=state.get('location','');current=state.get('current','')
        detail=' · '.join(s for s in [location,current] if s)
        if state.get('part_total',0):detail+=f" · muestra {state.get('part_done',0)}/{state['part_total']}"
        if state.get('errors',0):detail+=f" · {state['errors']} errores (ver Actividad)"
        self.detail.set_text(detail);self.detail.set_visible(bool(detail))
        self.set_tooltip_text(phase+('\n'+detail if detail else ''))
        self.pulsing=running and not paused and not known and stage not in ('waiting_model','error') and not phase.startswith('Esperando GPU')
        if self.pulsing and self.timer is None:self.timer=GLib.timeout_add(120,self.pulse)
        if not self.pulsing and self.timer is not None:GLib.source_remove(self.timer);self.timer=None
    def pulse(self):
        if not self.pulsing:self.timer=None;return False
        if self.get_visible():self.bar.pulse()
        return True
    def close(self):
        self.pulsing=False
        if self.timer is not None:GLib.source_remove(self.timer);self.timer=None
