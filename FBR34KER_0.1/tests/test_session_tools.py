from __future__ import annotations
import json, pathlib, subprocess, sys, tempfile, unittest
from host.session_bundle import STANDARD_FILES, write_session_bundle
ROOT=pathlib.Path(__file__).resolve().parents[1]

class SessionToolsTests(unittest.TestCase):
    def bundle(self,path):
        summary={'schema_version':1,'project':'FBR34KER','release_version':'0.2.3','session_id':'1'*24,'profile_id':'p','device':{},'adapter':{},'image':{},'stages':[{'stage':'console','status':'passed'}],'passed':True}
        values={name:(summary if name in {'session.json','summary.json'} else {'records':[{'operation':'start','status':'passed'}]} if name=='trace.json' else {} if name.endswith('.json') else 'hello\n' if name=='console.log' else '') for name in STANDARD_FILES}
        write_session_bundle(path,values)
    def test_inspect_replay_trace_and_crash(self):
        with tempfile.TemporaryDirectory() as d:
            bundle=pathlib.Path(d)/'session.zip'; self.bundle(bundle)
            for args in [['inspect',str(bundle)],['replay',str(bundle),'--console-only'],['trace-timeline',str(bundle)],['crash-decode',str(bundle)]]:
                result=subprocess.run([sys.executable,'host/session_tools.py',*args],cwd=ROOT,text=True,capture_output=True)
                self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__': unittest.main()
