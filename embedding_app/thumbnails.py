"""Bounded local thumbnail cache. No models, no remote requests."""
import hashlib
import shutil
import subprocess
from pathlib import Path


def thumbnail(store, file_id, position=None):
    from PIL import Image, ImageOps
    with store.connect() as c:
        row = c.execute('SELECT * FROM files WHERE id=?', (file_id,)).fetchone()
    if row is None:
        return None
    position = max(0, float(position or 0))
    key = hashlib.sha256(f"{row['id']}:{row['mtime_ns']}:{row['size']}:{position:.2f}".encode()).hexdigest()
    cache = store.directory / 'thumbnails'
    cache.mkdir(exist_ok=True)
    dest = cache / (key + '.jpg')
    if dest.exists():
        return str(dest)
    source = Path(row['path'])
    if not source.is_file():
        return None
    temp = cache / (key + '.tmp.jpg')
    try:
        if row['kind'] == 'image':
            with Image.open(source) as image:
                image = ImageOps.exif_transpose(image)
                image.thumbnail((720, 450))
                image.convert('RGB').save(temp, 'JPEG', quality=82)
        elif row['kind'] == 'video':
            subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-ss', str(position),
                            '-i', str(source), '-frames:v', '1', '-vf',
                            "scale='min(720,iw)':-2", '-y', str(temp)],
                           check=True, timeout=12)
        elif source.suffix.lower() == '.pdf' and shutil.which('pdftoppm'):
            prefix = cache / (key + '.pdf-preview')
            subprocess.run(['pdftoppm', '-f', '1', '-singlefile', '-scale-to', '720',
                            '-jpeg', str(source), str(prefix)], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=12)
            prefix.with_suffix('.pdf-preview.jpg').replace(temp)
        else:
            return None
        if temp.exists():
            temp.replace(dest)
            return str(dest)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    finally:
        temp.unlink(missing_ok=True)
    return None
