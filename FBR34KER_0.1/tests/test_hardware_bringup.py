from __future__ import annotations
import json, pathlib, shlex, subprocess, sys, tempfile, unittest, zipfile
from host.boot_image import Component, build_image
ROOT=pathlib.Path(__file__).resolve().parents[1]

class HardwareBringupTests(unittest.TestCase):
    def fixture(self, root):
        monitor=root/'monitor.bin'; monitor.write_bytes(b'B'*4096)
        image=root/'boot.img'; build_image(image,ROOT/'profiles/apple-a13-recovery.json',[Component('monitor',monitor,0x80000000,0x80000000)])
        device=root/'device.json'; device.write_text(json.dumps({'cpid':'0x8030','mode':'DFU','ecid':'abcd'}))
        return image,device
    def command(self,root,image,device,*extra):
        return [sys.executable,'host/hardware_bringup.py','run','--state-dir',str(root/'state'),'--device-info',str(device),'--profile','profiles/apple-a13-recovery.json','--image',str(image),'--authorized-session','--authorization-id','authorized-test-session','--acknowledge-unsigned-code',*extra]
    def test_complete_simulated_bringup(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d); image,device=self.fixture(root); evidence=root/'evidence.zip'
            result=subprocess.run(self.command(root,image,device,'--evidence',str(evidence)),cwd=ROOT,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr); self.assertTrue(evidence.is_file())
            with zipfile.ZipFile(evidence) as z: summary=json.loads(z.read('summary.json'))
            self.assertTrue(summary['passed']); self.assertEqual(len(summary['stages']),7)
    def test_failure_recovers_and_requires_reauthorization(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d); image,device=self.fixture(root); evidence=root/'failure.zip'
            result=subprocess.run(self.command(root,image,device,'--inject-failure','timer','--evidence',str(evidence)),cwd=ROOT,text=True,capture_output=True)
            self.assertEqual(result.returncode,1,result.stderr)
            summary=json.loads(result.stdout); self.assertFalse(summary['passed']); self.assertTrue(summary['authorization_invalidated_after_recovery'])
            result2=subprocess.run(self.command(root,image,device),cwd=ROOT,text=True,capture_output=True)
            self.assertEqual(result2.returncode,0,result2.stderr)

    def test_persistent_bridge_exact_profile(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d)
            monitor=root/'monitor.bin'; monitor.write_bytes(b'C'*4096)
            image=root/'boot.img'; build_image(image,ROOT/'profiles/apple-a13-iphone-recovery.json',[Component('monitor',monitor,0x80000000,0x80000000)])
            device=root/'device.json'; device.write_text(json.dumps({'cpid':'0x8030','mode':'DFU','ecid':'abcd','product':'iPhone12,1'}))
            bridge=shlex.join([sys.executable,str(ROOT/'host/reference_bridge.py'),'--state-dir',str(root/'bridge-state'),'--device-info',str(device)])
            evidence=root/'physical-session.zip'
            command=[sys.executable,'host/hardware_bringup.py','run','--state-dir',str(root/'unused'),'--device-info',str(device),'--profile','profiles/apple-a13-iphone-recovery.json','--image',str(image),'--bridge-command',bridge,'--authorized-session','--authorization-id','authorized-test-session','--acknowledge-unsigned-code','--evidence',str(evidence)]
            result=subprocess.run(command,cwd=ROOT,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr); self.assertTrue(evidence.is_file())
            with zipfile.ZipFile(evidence) as bundle:
                self.assertIn('checksums.sha256',bundle.namelist()); self.assertIn('console.log',bundle.namelist())

if __name__=='__main__': unittest.main()
