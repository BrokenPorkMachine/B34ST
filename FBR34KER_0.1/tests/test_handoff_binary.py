import json, pathlib, tempfile, unittest, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"host"))
from handoff_binary import build_blob, inspect_blob, roundtrip_blob, HandoffBinaryError

class HandoffBinaryTests(unittest.TestCase):
    def test_build_inspect_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td)/"h.fbhb"; p.write_bytes(build_blob(ROOT/"examples/handoff-v4.json"))
            info=inspect_blob(p)
            self.assertEqual(info["abi_version"],4)
            self.assertEqual(info["sections"]["handoff"]["size"],284)
            self.assertFalse(info["runtime_ready"])
            self.assertTrue(roundtrip_blob(p)["roundtrip_equal"])
    def test_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td)/"h.fbhb"; data=bytearray(build_blob(ROOT/"examples/handoff-v4.json")); data[-1]^=1; p.write_bytes(data)
            with self.assertRaises(HandoffBinaryError): inspect_blob(p)
