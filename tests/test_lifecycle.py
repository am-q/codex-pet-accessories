import json,sys,tempfile,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from pet_lifecycle import should_auto_start,exit_reason,log_event,status,task_name

class LifecycleTests(unittest.TestCase):
    def test_auto_start_requires_all_three_conditions(self):
        for enabled in (False,True):
            for alive in (False,True):
                for pet in (None,{'open':False},{'open':True}):
                    self.assertEqual(should_auto_start({'auto_start':enabled},alive,pet),
                                     enabled and alive and bool(pet and pet['open']))
    def test_codex_exit_always_closes_but_pet_toggle_obeys_setting(self):
        self.assertEqual(exit_reason(False,{'open':True},False),'codex_exit')
        self.assertEqual(exit_reason(True,{'open':False},True),'pet_closed')
        self.assertIsNone(exit_reason(True,{'open':False},False))
        self.assertIsNone(exit_reason(True,None,True))
    def test_exit_evidence_is_retained_separately_from_startup(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)
            log_event(p,'starting',automatic=True)
            log_event(p,'closed',reason='codex_exit')
            status(p,'closed',reason='codex_exit')
            self.assertEqual([json.loads(x)['event'] for x in (p/'lifecycle.log').read_text('utf-8').splitlines()],['starting','closed'])
            self.assertEqual(json.loads((p/'runtime.json').read_text('utf-8'))['reason'],'codex_exit')
            self.assertFalse((p/'startup.json').exists())
    def test_task_identity_is_per_installation(self):
        self.assertEqual(task_name('local-data'),task_name(Path.cwd()/'local-data'))
        self.assertNotEqual(task_name('local-data'),task_name('other-data'))
