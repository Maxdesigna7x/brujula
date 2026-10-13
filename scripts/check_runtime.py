import importlib, importlib.metadata, sys
names={'torchvision':'torchvision','torch':'torch','transformers':'transformers','sentence-transformers':'sentence_transformers','pypdf':'pypdf','python-docx':'docx','Pillow':'PIL','soundfile':'soundfile'}
errors=[]
for package,module in names.items():
    try:
        importlib.import_module(module);print(package,importlib.metadata.version(package))
    except Exception as exc:errors.append(f'{package}: {exc}')
try:
    from transformers import EmbeddingGemma2Model
except Exception as exc:errors.append('EmbeddingGemma2Model: '+str(exc))
# uv pip check ignores shared system-site-packages; validate the effective runtime.
from packaging.requirements import Requirement
from importlib.metadata import requires,version,PackageNotFoundError
for package in ['transformers','sentence-transformers','soundfile','tokenizers','safetensors','pypdf']:
    for raw in requires(package) or []:
        req=Requirement(raw)
        if req.marker and not req.marker.evaluate({'extra':''}):continue
        try:
            installed=version(req.name)
            if req.specifier and installed not in req.specifier:errors.append(f'{req.name}: {installed} no cumple {req.specifier}')
        except PackageNotFoundError:errors.append('Falta dependencia: '+req.name)
if errors:print('\n'.join(errors),file=sys.stderr);raise SystemExit(1)
print('Runtime listo.')
