import os,tempfile,subprocess,unittest,wave,time
from pathlib import Path
import numpy as np
from PIL import Image
from embedding_app.backend import Backend
from embedding_app.storage import Store
from embedding_app.volumes import add_location
from embedding_app.indexer import Indexer
from embedding_app.inference import fingerprint
from embedding_app.thumbnails import thumbnail

class SpyEncoder:
    def __init__(self):self.items=[]
    def encode(self,items,settings,query=False):
        self.items.extend(items)
        for item in items:
            if item['modality']!='text':assert Path(item['value']).exists()
        return [np.array([1,0]+[0]*254,dtype='<f4').tobytes() for _ in items]
    def close(self):pass

class MediaTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.docs=self.root/'indexed';self.docs.mkdir()
        self.store=Store(self.root/'db');self.backend=Backend(self.store);self.backend.end.set();self.backend.encoder=SpyEncoder()
        Image.new('RGB',(320,200),'blue').save(self.docs/'photo.png');(self.docs/'notes.txt').write_text('example')
        add_location(self.store,self.docs);self.backend.indexer.scan(self.store.settings())
        with self.store.connect() as c:
            rows=c.execute('SELECT id,name FROM files').fetchall();self.ids={r['name']:r['id'] for r in rows}
            for r in rows:
                vector=np.array(([1,0] if r['name']=='photo.png' else [0,1])+[0]*254,dtype='<f4').tobytes()
                c.execute('INSERT INTO segments(file_id,modality,vector,dim,model) VALUES (?,?,?,?,?)',(r['id'],'image' if r['name']=='photo.png' else 'text',vector,256,fingerprint(256)))
    def tearDown(self):self.backend.close();self.temp.cleanup()
    def test_image_query_uses_content_and_is_not_indexed(self):
        source=self.root/'input.png';Image.new('RGB',(1600,1200),'blue').save(source)
        result=self.backend.dispatch('search',query_input={'modality':'image','path':str(source)})
        self.assertEqual(result['results'][0]['name'],'photo.png')
        self.assertEqual(self.backend.encoder.items[0]['modality'],'image')
        self.assertFalse(Path(self.backend.encoder.items[0]['value']).exists())
        with self.store.connect() as c:self.assertEqual(c.execute('SELECT count(*) FROM files').fetchone()[0],2)
    def test_audio_query_preprocessing_and_invalid_input(self):
        source=self.root/'audio.wav'
        with wave.open(str(source),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(np.zeros(16000,dtype='<i2').tobytes())
        result=self.backend.dispatch('search',query_input={'modality':'audio','path':str(source)})
        self.assertIn('audio',result['mode']);self.assertEqual(self.backend.encoder.items[0]['modality'],'audio')
        with self.assertRaises(ValueError):self.backend.dispatch('search',query_input={'modality':'video','path':str(source)})
    def test_thumbnails_cache_and_disconnected_source(self):
        dest=thumbnail(self.store,self.ids['photo.png']);self.assertTrue(Path(dest).exists())
        (self.docs/'photo.png').unlink();self.assertEqual(thumbnail(self.store,self.ids['photo.png']),dest)
        self.assertIsNone(thumbnail(self.store,self.ids['notes.txt']))
    def test_video_and_pdf_thumbnails(self):
        video=self.docs/'clip.mp4'
        subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i','color=c=red:s=320x200:d=1','-pix_fmt','yuv420p','-y',str(video)],check=True,timeout=20)
        Image.new('RGB',(300,400),'white').save(self.docs/'page.pdf')
        self.backend.indexer.scan(self.store.settings())
        with self.store.connect() as c:ids={r['name']:r['id'] for r in c.execute('SELECT id,name FROM files')}
        self.assertTrue(Path(thumbnail(self.store,ids['clip.mp4'],.4)).exists())
        import shutil
        if shutil.which('pdftoppm'):self.assertTrue(Path(thumbnail(self.store,ids['page.pdf'])).exists())

if __name__=='__main__':unittest.main()
