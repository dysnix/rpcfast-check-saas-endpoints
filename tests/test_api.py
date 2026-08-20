import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


async def successful_check(*args):
    return {"status": "ok"}


class ApiTests(unittest.TestCase):
    def test_saas_runs_all_supported_checks(self):
        check_names = (
            "check_jsonrpc_http",
            "check_jsonrpc_ws",
            "check_yellowstone",
            "check_shredstream",
            "check_aperture_txstream",
            "check_aperture_simulation",
            "check_beam_http",
            "check_beam_quic",
        )
        patches = [
            patch(f"app.main.{name}", new=successful_check) for name in check_names
        ]

        for active_patch in patches:
            active_patch.start()
        try:
            response = TestClient(app).post(
                "/api/check",
                json={"http_token": "token", "endpoint_type": "saas"},
            )
        finally:
            for active_patch in reversed(patches):
                active_patch.stop()

        self.assertEqual(response.status_code, 200)
        result_checks = set()
        for line in response.text.splitlines():
            if line.startswith("data: "):
                payload = json.loads(line.removeprefix("data: "))
                if payload.get("check") and payload.get("status") == "ok":
                    result_checks.add(payload["check"])

        self.assertEqual(
            result_checks,
            {
                "jsonrpc_http",
                "jsonrpc_ws",
                "yellowstone_grpc",
                "shredstream_grpc",
                "aperture_txstream_grpc",
                "aperture_simulation_grpc",
                "beam_http",
                "beam_quic",
            },
        )
