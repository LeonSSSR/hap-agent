from __future__ import annotations

import socket
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformServiceTarget:
    name: str
    host: str
    port: int


class PlatformProbe:
    """Read-only TCP connect probe for platform service ports."""

    CHECK_TYPE = "tcp_connect"
    DEFAULT_TIMEOUT_SECONDS = 0.5

    def __init__(self, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self.timeout_seconds = timeout_seconds
        self.targets = [
            PlatformServiceTarget(name="core-service", host="127.0.0.1", port=8085),
            PlatformServiceTarget(name="nginx/api-gateway", host="127.0.0.1", port=8086),
            PlatformServiceTarget(name="agent-service", host="127.0.0.1", port=8010),
            PlatformServiceTarget(name="pipeline-proxy", host="127.0.0.1", port=8700),
            PlatformServiceTarget(name="notebook-proxy", host="127.0.0.1", port=8800),
            PlatformServiceTarget(name="kserve-proxy", host="127.0.0.1", port=8600),
        ]

    def probe_all(self) -> dict[str, object]:
        services = [self._probe_target(target) for target in self.targets]
        healthy_count = sum(1 for service in services if service["reachable"])
        return {
            "summary": "v7 真实只读 TCP 端口检测完成",
            "read_only": True,
            "source": "socket_tcp_connect_probe",
            "check_type": self.CHECK_TYPE,
            "total": len(services),
            "healthy": healthy_count,
            "down": len(services) - healthy_count,
            "services": services,
        }

    def _probe_target(self, target: PlatformServiceTarget) -> dict[str, object]:
        started_at = time.perf_counter()
        reachable = False
        error_message = ""

        try:
            with socket.create_connection(
                (target.host, target.port),
                timeout=self.timeout_seconds,
            ):
                reachable = True
        except OSError as exc:
            error_message = exc.__class__.__name__

        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        status = "healthy" if reachable else "down"
        note = (
            "TCP connect succeeded; read-only probe only, no service mutation performed."
            if reachable
            else f"TCP connect failed with {error_message}; read-only probe only, no remediation performed."
        )

        return {
            "name": target.name,
            "host": target.host,
            "port": target.port,
            "status": status,
            "reachable": reachable,
            "latency_ms": latency_ms,
            "check_type": self.CHECK_TYPE,
            "read_only": True,
            "note": note,
        }
