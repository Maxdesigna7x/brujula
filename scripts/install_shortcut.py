#!/usr/bin/python3
"""Install/remove our shortcut without overwriting existing custom bindings."""
import argparse
from pathlib import Path
from gi.repository import Gio
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--remove',action='store_true');args=parser.parse_args()
path='/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/brujula/'
settings=Gio.Settings.new('org.gnome.settings-daemon.plugins.media-keys')
custom=Gio.Settings.new_with_path('org.gnome.settings-daemon.plugins.media-keys.custom-keybinding',path)
paths=list(settings.get_strv('custom-keybindings'))
if args.remove:
    settings.set_strv('custom-keybindings',[p for p in paths if p!=path])
    for key in ['name','command','binding']:custom.reset(key)
    print('Atajo de Brújula eliminado.')
else:
    binding='<Control><Alt>space'
    def normalize(value):return value.lower().replace('<primary>','<control>').replace('<ctrl>','<control>')
    for other in paths:
        if other==path:continue
        s=Gio.Settings.new_with_path('org.gnome.settings-daemon.plugins.media-keys.custom-keybinding',other)
        if normalize(s.get_string('binding'))==normalize(binding):
            raise SystemExit('Ctrl+Alt+Space ya tiene otro atajo. Configura Brújula manualmente para preservarlo.')
    custom.set_string('name','Brújula · búsqueda rápida');custom.set_string('command',str(root/'run.sh'));custom.set_string('binding',binding)
    if path not in paths:settings.set_strv('custom-keybindings',paths+[path])
    print('Ctrl+Alt+Space abre Brújula.')
Gio.Settings.sync()
