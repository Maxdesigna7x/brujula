import os, tempfile, time, unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from embedding_app.storage import Store
from embedding_app.volumes import add_location,refresh_locations
from embedding_app.indexer import Indexer
from embedding_app.search import search
from embedding_app.readers import select_text,positions
from embedding_app.inference import fingerprint

class FakeEncoder:
    def encode(self,items,settings,query=False):return [np.array([1,0]+[0]*254,dtype='<f4').tobytes() for _ in items]
    def close(self):pass

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name);self.docs=self.base/'docs';self.docs.mkdir()
        self.store=Store(self.base/'db');self.encoder=FakeEncoder();self.indexer=Indexer(self.store,self.encoder)
        self.lid=add_location(self.store,self.docs)
    def tearDown(self):self.tmp.cleanup()
    def scan(self):self.indexer.scan(self.store.settings())
    def test_scope_exclusions_and_changed_content(self):
        (self.docs/'informe.txt').write_text('gatos');(self.docs/'.env').write_text('secret')
        (self.docs/'node_modules').mkdir();(self.docs/'node_modules/leak.txt').write_text('hidden')
        (self.docs/'linked.txt').symlink_to(self.docs/'informe.txt');self.scan()
        with self.store.connect() as c:
            rows=c.execute('SELECT * FROM files').fetchall();self.assertEqual(len(rows),1);fid=rows[0]['id']
            c.execute("UPDATE files SET status='ready' WHERE id=?",(fid,))
            c.execute('INSERT INTO segments(file_id,modality,vector,dim,model) VALUES (?,?,?,?,?)',(fid,'text',b'x',256,'old'))
        (self.docs/'informe.txt').write_text('perros y gatos');self.scan()
        with self.store.connect() as c:
            self.assertEqual(c.execute('SELECT status FROM files').fetchone()[0],'pending');self.assertEqual(c.execute('SELECT count(*) FROM segments').fetchone()[0],0)
        (self.docs/'informe.txt').unlink();self.scan()
        with self.store.connect() as c:self.assertEqual(c.execute('SELECT count(*) FROM files').fetchone()[0],0)
    def test_exact_filters_and_empty_zone(self):
        (self.docs/'Vídeo de Linux.txt').write_text('linux');self.scan()
        self.assertEqual(len(search(self.store,self.encoder,'video',{'locations':[self.lid]})['results']),1)
        self.assertEqual(search(self.store,self.encoder,'video',{'locations':[]})['results'],[])
        self.assertEqual(search(self.store,self.encoder,'',{'min_size':100})['results'],[])
        self.assertEqual(search(self.store,self.encoder,'',{'folder':str(self.docs)+'x'})['results'],[])
        self.assertEqual(len(search(self.store,self.encoder,'',{'folder':str(self.docs)})['results']),1)
    def test_semantic_search_respects_location_model_and_dimension(self):
        (self.docs/'primero.txt').write_text('a');self.scan()
        second=self.base/'second';second.mkdir();(second/'segundo.txt').write_text('b');lid2=add_location(self.store,second);self.scan()
        with self.store.connect() as c:
            for r in c.execute('SELECT id FROM files').fetchall():c.execute('INSERT INTO segments(file_id,modality,vector,dim,model) VALUES (?,?,?,?,?)',(r[0],'text',np.array([1,0]+[0]*254,dtype='<f4').tobytes(),256,fingerprint(256)))
        with patch('embedding_app.search.ready',return_value=True):
            results=search(self.store,self.encoder,'tema',{'locations':[self.lid]})['results'];self.assertEqual([r['location_id'] for r in results],[self.lid])
    def test_disconnected_disk_preserved_and_remount(self):
        (self.docs/'keep.txt').write_text('a');self.scan()
        with self.store.connect() as c:c.execute("UPDATE locations SET volume='external',relative='docs',mount=? WHERE id=?",(str(self.base),self.lid))
        with patch('embedding_app.volumes.volumes',return_value=[]):self.scan()
        self.assertFalse(self.store.locations()[0]['online'])
        self.assertEqual(len(search(self.store,self.encoder,'',{})['results']),1)
        self.assertEqual(search(self.store,self.encoder,'',{'offline':False})['results'],[])
        mount=self.base/'remount';mount.mkdir();self.docs.rename(mount/'docs')
        with patch('embedding_app.volumes.volumes',return_value=[{'uuid':'external','mount':str(mount),'name':'Disk','size':1}]):refresh_locations(self.store)
        with self.store.connect() as c:self.assertEqual(c.execute('SELECT path FROM files').fetchone()[0],str(mount/'docs/keep.txt'))
    def test_multiple_segments_do_not_accumulate_semantic_bonus(self):
        for name in ['alpha.txt','beta.txt']:(self.docs/name).write_text('sample')
        self.scan()
        with self.store.connect() as c:
            files={r['name']:r['id'] for r in c.execute('SELECT id,name FROM files')}
            for name,similarity,count in [('alpha.txt',.8,1),('beta.txt',.75,3)]:
                v=np.array([similarity,(1-similarity**2)**.5]+[0]*254,dtype='<f4').tobytes()
                for _ in range(count):c.execute('INSERT INTO segments(file_id,modality,vector,dim,model) VALUES (?,?,?,?,?)',(files[name],'text',v,256,fingerprint(256)))
        with patch('embedding_app.search.ready',return_value=True):
            result=search(self.store,self.encoder,'unrelated',{})
        self.assertEqual(result['results'][0]['name'],'alpha.txt')
        self.assertAlmostEqual(result['results'][1]['score'],.75,places=5)
    def test_incomplete_scan_does_not_delete_records(self):
        (self.docs/'keep.txt').write_text('sample');self.scan()
        def failed_walk(*args,**kwargs):
            kwargs['onerror'](PermissionError('unreadable'));return iter([])
        with patch('embedding_app.indexer.os.walk',side_effect=failed_walk):self.scan()
        with self.store.connect() as c:self.assertEqual(c.execute('SELECT count(*) FROM files').fetchone()[0],1)
    def test_incremental_index_processes_only_new_and_modified_files(self):
        class CountingEncoder(FakeEncoder):
            count=0
            def encode(self,items,settings,query=False):
                self.count+=len(items)
                return super().encode(items,settings,query)
        encoder=CountingEncoder();indexer=Indexer(self.store,encoder)
        self.store.update_settings({'gpu_idle_only':False})
        def write(name,text):
            p=self.docs/name;p.write_text(text);os.utime(p,(time.time()-20,time.time()-20))
        write('one.txt','Linux');write('two.txt','Chocolate')
        with patch('embedding_app.indexer.ready',return_value=True),patch('embedding_app.indexer.engine_python',return_value=Path('/mock/python')):
            indexer.run();initial=encoder.count;self.assertEqual(initial,4)
            indexer.run();self.assertEqual(encoder.count,initial)
            write('three.txt','Montañas');indexer.run();self.assertEqual(encoder.count,initial+2)
            write('one.txt','Linux Ubuntu installation');indexer.run();self.assertEqual(encoder.count,initial+4)
    def test_zone_and_overlap(self):
        self.store.zone('Trabajo',[self.lid]);self.assertEqual(self.store.zones()[0]['locations'],[self.lid])
        child=self.docs/'sub';child.mkdir()
        with self.assertRaises(ValueError):add_location(self.store,child)
        self.store.remove_location(self.lid);self.assertEqual(self.store.zones()[0]['locations'],[])
    def test_sampling_spans_document_and_media(self):
        text=select_text(' '.join('word'+str(i) for i in range(9000)),300)
        self.assertIn('word0',text);self.assertIn('word4500',text);self.assertIn('word8999',text)
        pts=positions(7200,4,20);self.assertEqual(len(pts),4);self.assertGreater(pts[-1],6000);self.assertLess(pts[-1]+20,7200)

if __name__=='__main__':unittest.main()
