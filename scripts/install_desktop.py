"""Install launchers only. Does not enable services or change shortcuts."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
applications=Path.home()/'.local/share/applications';applications.mkdir(parents=True,exist_ok=True)
text=f'''[Desktop Entry]
Type=Application
Name=Brújula
Comment=Busca tus archivos por significado, disco y zona
Exec="{root / 'run.sh'}"
Icon={root / 'assets/brujula.svg'}
Terminal=false
Categories=Utility;FileTools;
StartupNotify=true
'''
(applications/'local.brujula.search.desktop').write_text(text)
print('Brújula instalada en el menú de aplicaciones.')
