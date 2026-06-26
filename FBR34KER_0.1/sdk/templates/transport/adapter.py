"""Authorized {{NAME}} FBDP transport adapter template."""
from __future__ import annotations
from host.deployment_transport import DeploymentTransport, TransportError

class {{UPPER}}Transport(DeploymentTransport):
    def exchange(self, frame, timeout: float):
        raise TransportError("{{NAME}} adapter is not implemented")
    def close(self) -> None:
        pass
