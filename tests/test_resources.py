import unittest
from types import SimpleNamespace
from unittest.mock import patch
from embedding_app.resources import decision, ResourceGate, gpu_snapshot
from embedding_app.storage import DEFAULTS

class ResourceTests(unittest.TestCase):
    def setUp(self):
        self.settings=dict(DEFAULTS)
        self.idle={'available':True,'utilization':0,'free_mb':4000,'total_mb':12000}
    def test_busy_gpu_or_low_memory_defers_indexing(self):
        self.assertFalse(decision(self.settings,self.idle|{'utilization':80})[0])
        self.assertFalse(decision(self.settings,self.idle|{'free_mb':1000})[0])
        self.assertTrue(decision(self.settings,self.idle)[0])
    def test_own_weights_are_reclaimable_but_external_usage_is_not(self):
        snap=self.idle|{'free_mb':1500}
        self.assertFalse(decision(self.settings,snap)[0])
        self.assertTrue(decision(self.settings,snap,own_mb=1600)[0])
    def test_cpu_and_disabled_guard_do_not_require_nvidia(self):
        unknown={'available':False}
        self.assertFalse(decision(self.settings,unknown)[0])
        self.assertTrue(decision(self.settings|{'device':'cpu'},unknown)[0])
        self.assertTrue(decision(self.settings|{'gpu_idle_only':False},unknown)[0])
    def test_busy_then_idle_releases_model_and_resumes(self):
        self.settings['gpu_check_seconds']=.01
        encoder=SimpleNamespace(process=None,last=0,close=lambda:closed.append(True))
        closed=[];state={};gate=ResourceGate()
        with patch('embedding_app.resources.gpu_snapshot',side_effect=[self.idle|{'utilization':80},self.idle]):
            gate.wait(lambda:self.settings,encoder,state,lambda:None)
        self.assertEqual(closed,[True]);self.assertEqual(state['phase'],'Analizando contenido')
        self.assertTrue(gate.last['allowed'])
    def test_wait_is_interruptible(self):
        encoder=SimpleNamespace(process=None,last=0,close=lambda:None)
        checkpoints=[]
        def checkpoint():
            checkpoints.append(1)
            if len(checkpoints)>1:raise InterruptedError()
        with patch('embedding_app.resources.gpu_snapshot',return_value=self.idle|{'utilization':90}):
            with self.assertRaises(InterruptedError):ResourceGate().wait(lambda:self.settings,encoder,{},checkpoint)
    def test_nvidia_probe_is_bounded_and_parses_values(self):
        with patch('embedding_app.resources.subprocess.check_output',return_value='12, 4096, 12288\n') as call:
            self.assertEqual(gpu_snapshot()['free_mb'],4096)
            self.assertEqual(call.call_args.kwargs['timeout'],5)

if __name__=='__main__':unittest.main()
