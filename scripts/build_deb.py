"""Build an architecture-independent .deb, without root or personal data."""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from embedding_app import __version__

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'dist');args=parser.parse_args()
    staging=ROOT/'work/deb-build'
    if staging.exists():shutil.rmtree(staging)
    source=staging/'usr/share/brujula';source.mkdir(parents=True)
    for folder in ['embedding_app','scripts','docs','assets','examples']:
        shutil.copytree(ROOT/folder,source/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.log'))
    for name in ['README.md','requirements.txt','requirements-runtime.txt','run.sh','cli.sh']:
        shutil.copy2(ROOT/name,source/name)
    binaries=staging/'usr/bin';binaries.mkdir(parents=True);shutil.copy2(ROOT/'packaging/brujula',binaries/'brujula')
    desktop=staging/'usr/share/applications';desktop.mkdir(parents=True);shutil.copy2(ROOT/'packaging/brujula.desktop',desktop/'local.brujula.search.desktop')
    icons=staging/'usr/share/icons/hicolor/scalable/apps';icons.mkdir(parents=True);shutil.copy2(ROOT/'assets/brujula.svg',icons/'brujula.svg')
    debian=staging/'DEBIAN';debian.mkdir();control=(ROOT/'packaging/control.in').read_text().replace('@VERSION@',__version__)
    installed=sum(p.stat().st_size for p in staging.rglob('*') if p.is_file())//1024+1
    (debian/'control').write_text(control+f'Installed-Size: {installed}\n')
    for p in staging.rglob('*'):
        if p.is_dir():p.chmod(0o755)
        elif p==binaries/'brujula' or p.suffix=='.sh':p.chmod(0o755)
        else:p.chmod(0o644)
    epoch=int(os.environ.get('SOURCE_DATE_EPOCH',subprocess.check_output(['git','log','-1','--format=%ct'],cwd=ROOT,text=True).strip()))
    for p in sorted(staging.rglob('*'),reverse=True):os.utime(p,(epoch,epoch),follow_symlinks=False)
    os.utime(staging,(epoch,epoch))
    args.output.mkdir(parents=True,exist_ok=True);package=args.output/f'brujula_{__version__}_all.deb'
    subprocess.run(['dpkg-deb','--root-owner-group','-Zxz','-z6','--build',str(staging),str(package)],check=True,env=os.environ|{'SOURCE_DATE_EPOCH':str(epoch)})
    with package.open('rb') as f:checksum=hashlib.file_digest(f,'sha256').hexdigest()
    (args.output/(package.name+'.sha256')).write_text(checksum+'  '+package.name+'\n')
    print(package)
if __name__=='__main__':main()
