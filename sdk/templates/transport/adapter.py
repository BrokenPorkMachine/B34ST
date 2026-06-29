"""Authorized FBDP transport adapter template.

Replace TRANSPORT_NAME and TRANSPORT_NAME_UPPER with the target transport name,
then implement the exchange() method using the actual transport mechanism.
"""

from __future__ import annotations

import pathlib
from host.deployment_transport import DeploymentTransport, TransportError


class TRANSPORT_NAMETransport(DeploymentTransport):
    def exchange(self, frame, timeout: float):
        raise TransportError("TRANSPORT_NAME adapter exchange is not implemented")

    def close(self) -> None:
        pass
