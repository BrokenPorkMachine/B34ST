from __future__ import annotations
import pathlib, tempfile, unittest
from host.session_bundle import STANDARD_FILES, read_session_bundle, verify_session_bundle, write_session_bundle

class SessionBundleTests(unittest.TestCase):
    def values(self):
        summary={'schema_version':1,'project':'FBR34KER','release_version':'0.4.3b','session_id':'0'*24,'profile_id':'p','device':{},'adapter':{},'image':{},'stages':[],'passed':True}
        return {name:(summary if name in {'session.json','summary.json'} else {} if name.endswith('.json') else '') for name in STANDARD_FILES}
    def test_bundle_is_deterministic_and_verified(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d); a=root/'a.zip'; b=root/'b.zip'
            write_session_bundle(a,self.values()); write_session_bundle(b,self.values())
            self.assertEqual(a.read_bytes(),b.read_bytes())
            result=verify_session_bundle(a); self.assertTrue(result['valid'],result)
            self.assertIn('console.log',read_session_bundle(a))

if __name__=='__main__': unittest.main()
