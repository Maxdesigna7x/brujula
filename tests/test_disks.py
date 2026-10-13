import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from embedding_app.storage import Store
from embedding_app.volumes import add_location,set_disk,disk_states
from embedding_app.indexer import Indexer
class Encoder:
    def close(self):pass
class DiskTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name);self.mount=self.base/'disk';self.mount.mkdir()
        self.store=Store(self.base/'db');self.disk={'uuid':'test-disk','mount':str(self.mount),'name':'Ejemplo','size':1000}
        self.mock=patch('embedding_app.volumes.volumes',return_value=[dict(self.disk)]);self.mock.start()
        self.indexer=Indexer(self.store,Encoder())
    def tearDown(self):self.mock.stop();self.tmp.cleanup()
    def test_empty_partial_whole_disabled_and_no_duplicate_files(self):
        self.assertFalse(disk_states(self.store)[0]['included'])
        child=self.mount/'Docs';child.mkdir();(child/'one.txt').write_text('one');(self.mount/'two.txt').write_text('two')
        lid=add_location(self.store,child);self.indexer.scan(self.store.settings())
        with self.store.connect() as c:original=c.execute('SELECT id FROM files WHERE location_id=?',(lid,)).fetchone()[0]
        self.assertTrue(disk_states(self.store)[0]['partial'])
        set_disk(self.store,'test-disk',True);self.indexer.scan(self.store.settings())
        self.assertTrue(disk_states(self.store)[0]['whole'])
        with self.store.connect() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM files').fetchone()[0],2)
            self.assertEqual(c.execute('SELECT id FROM files WHERE name="one.txt"').fetchone()[0],original)
            c.execute('UPDATE locations SET enabled=0 WHERE id=?',(lid,))
        self.assertTrue(disk_states(self.store)[0]['partial'])
        set_disk(self.store,'test-disk',False)
        self.assertFalse(disk_states(self.store)[0]['included'])
        with self.store.connect() as c:self.assertEqual(c.execute('SELECT count(*) FROM files').fetchone()[0],2)
    def test_add_child_to_previously_indexed_whole_disk_preserves_records(self):
        child=self.mount/'Photos';child.mkdir();(child/'one.txt').write_text('one')
        set_disk(self.store,'test-disk',True);self.indexer.scan(self.store.settings())
        with self.store.connect() as c:
            original=c.execute('SELECT id FROM files').fetchone()[0];c.execute('UPDATE files SET important=1 WHERE id=?',(original,))
        lid=add_location(self.store,child);self.indexer.scan(self.store.settings())
        with self.store.connect() as c:
            r=c.execute('SELECT id,location_id,important,relative FROM files').fetchone()
            self.assertEqual(tuple(r),(original,lid,1,'one.txt'))
    def test_disconnected_disk_can_be_excluded_without_losing_cache(self):
        set_disk(self.store,'test-disk',True)
        with patch('embedding_app.volumes.volumes',return_value=[]):
            self.assertFalse(disk_states(self.store)[0]['online'])
            set_disk(self.store,'test-disk',False);self.assertFalse(disk_states(self.store)[0]['included'])
            with self.assertRaises(ValueError):set_disk(self.store,'new-disk',True)
if __name__=='__main__':unittest.main()
