from __future__ import annotations

import pathlib
import socket
import sys
import tempfile
import threading
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))

from deployment import DeploymentClient, LocalArtifact  # noqa: E402
from deployment_profile import load_profile  # noqa: E402
from deployment_server import serve_connection  # noqa: E402
from deployment_target import SimulatedDeploymentTarget  # noqa: E402
from deployment_transport import FramedStreamTransport, SocketEndpoint  # noqa: E402


class DeploymentStreamTests(unittest.TestCase):
    def test_idle_connection_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            profile = load_profile(ROOT / "profiles/qemu-virt-deployment.json")
            target = SimulatedDeploymentTarget(profile, root / "state")
            client_socket, server_socket = socket.socketpair()
            thread = threading.Thread(
                target=serve_connection, args=(server_socket, target),
                kwargs={"idle_timeout": 0.05}, daemon=True,
            )
            thread.start()
            thread.join(timeout=1.0)
            client_socket.close()
            server_socket.close()
            self.assertFalse(thread.is_alive())

    def test_socket_framed_deployment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            profile = load_profile(ROOT / "profiles/qemu-virt-deployment.json")
            target = SimulatedDeploymentTarget(profile, root / "state")
            monitor = root / "monitor.bin"
            monitor.write_bytes(b"socket-monitor" * 512)
            artifact = LocalArtifact.from_path("monitor", "monitor", monitor, 0x80000000)
            client_socket, server_socket = socket.socketpair()
            thread = threading.Thread(target=serve_connection,
                                      args=(server_socket, target), daemon=True)
            thread.start()
            client = DeploymentClient(
                FramedStreamTransport(SocketEndpoint(client_socket)),
                timeout=1.0, retries=1, chunk_size=1024,
            )
            try:
                result = client.deploy(profile, [artifact], authorize=True)
                self.assertTrue(result["started"])
            finally:
                client.close()
                thread.join(timeout=2.0)
                server_socket.close()
            self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main()
