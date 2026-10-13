"""Headless GTK visual verification with synthetic data only."""
import os, subprocess, time, sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
env=os.environ.copy();env['BRUJULA_DATA']=str(root/'work/ui-test-data');env['GSK_RENDERER']='cairo'
x=subprocess.Popen(['Xvfb',':94','-screen','0','1280x900x24']);env['DISPLAY']=':94'
try:
    time.sleep(1)
    app=subprocess.Popen([str(root/'run.sh')],cwd=root,env=env,stdout=subprocess.DEVNULL,stderr=(root/'work/ui-capture.log').open('w'))
    try:
        time.sleep(5)
        subprocess.run(['import','-window','root',str(root/'work/interface.png')],env=env,check=True)
    finally:app.terminate();app.wait(timeout=10)
finally:x.terminate();x.wait(timeout=5)
