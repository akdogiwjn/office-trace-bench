from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from office_trace_bench.artifact_capture import ArtifactCapture
from office_trace_bench.contracts import sha256

class ArtifactCaptureTests(unittest.TestCase):
    def test_rewritten_helper_versions_and_deleted_script_are_retained(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);workspace=root/'workspace';workspace.mkdir();temporary=root/'tmp';temporary.mkdir()
            monitor=ArtifactCapture(workspace,root/'capture',temporary).start()
            path=workspace/'helper.py';path.write_text('version one');first=sha256(path)
            deadline=time.monotonic()+3
            while not any(e.get('sha256')==first for e in monitor.events) and time.monotonic()<deadline:time.sleep(.01)
            path.write_text('version two');second=sha256(path)
            temp=temporary/'deleted.py';temp.write_text('temporary helper');third=sha256(temp)
            deadline=time.monotonic()+3
            while not any(e.get('sha256')==third for e in monitor.events) and time.monotonic()<deadline:time.sleep(.01)
            transformed=temporary/'intermediate.xlsx';transformed.write_bytes(b'original transformed-data bytes');fourth=sha256(transformed)
            deadline=time.monotonic()+3
            while not any(e.get('sha256')==fourth for e in monitor.events) and time.monotonic()<deadline:time.sleep(.01)
            transformed.unlink()
            temp.unlink();result=monitor.finish()
            hashes={e.get('sha256') for e in result['events']}
            self.assertTrue({first,second,third,fourth}<=hashes);self.assertFalse(result['replay_ready'])
            self.assertEqual(result['gaps'],[])
