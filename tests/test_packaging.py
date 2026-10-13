import json,os,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class PackagingTests(unittest.TestCase):
    def run_paths(self,directory,extra=None):
        code="from embedding_app.paths import DATA,model_directory,engine_python;import json;print(json.dumps({'data':str(DATA),'model':str(model_directory()),'engine':str(engine_python())}))"
        # Import from an installed-layout copy without a development venv.
        import shutil
        app=Path(directory)/'app';shutil.copytree(ROOT/'embedding_app',app/'embedding_app')
        env=os.environ|{'PYTHONPATH':str(app),'BRUJULA_DATA':str(Path(directory)/'data')}
        env.pop('BRUJULA_MODEL_DIR',None);env.pop('BRUJULA_ENGINE_PYTHON',None)
        env.update(extra or {})
        return json.loads(subprocess.check_output(['/usr/bin/python3','-c',code],cwd=app,env=env,text=True))
    def test_installed_layout_uses_writable_user_data(self):
        with tempfile.TemporaryDirectory() as d:
            result=self.run_paths(d)
            self.assertEqual(result['model'],str(Path(d)/'data/models/embeddinggemma-2'))
            self.assertEqual(result['engine'],'None')
    def test_explicit_external_runtime_and_model_remain_supported(self):
        with tempfile.TemporaryDirectory() as d:
            result=self.run_paths(d,{'BRUJULA_ENGINE_PYTHON':'/usr/bin/python3','BRUJULA_MODEL_DIR':'/tmp/custom-model'})
            self.assertEqual(result['engine'],'/usr/bin/python3');self.assertEqual(result['model'],'/tmp/custom-model')
if __name__=='__main__':unittest.main()
