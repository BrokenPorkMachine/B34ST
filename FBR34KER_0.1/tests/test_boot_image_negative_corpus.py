from __future__ import annotations
import pathlib, subprocess, sys, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class BootImageNegativeCorpusTests(unittest.TestCase):
    def test_deterministic_corpus_is_rejected(self):
        result=subprocess.run([sys.executable,'scripts/fuzz_boot_image.py','--iterations','16'],cwd=ROOT,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr); self.assertIn('rejected',result.stdout)
if __name__=='__main__': unittest.main()
