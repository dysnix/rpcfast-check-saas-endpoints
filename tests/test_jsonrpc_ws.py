import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from app.checks.jsonrpc_ws import check_jsonrpc_ws


class FakeSocket:
    def __init__(self, value):
        self.messages = [
            {"jsonrpc": "2.0", "id": 1, "result": 42},
            {
                "jsonrpc": "2.0",
                "method": "blockNotification",
                "params": {
                    "subscription": 42,
                    "result": {"context": {"slot": 100}, "value": value},
                },
            },
        ]
        self.sent = []
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.closed = True

    async def send(self, message):
        self.sent.append(json.loads(message))

    async def recv(self):
        return json.dumps(self.messages.pop(0))


class WebSocketTests(unittest.IsolatedAsyncioTestCase):
    async def test_v1_capability_and_block_metadata(self):
        socket = FakeSocket({"slot": 100, "block": {"blockHeight": 90}, "err": None})
        with (
            patch(
                "app.checks.jsonrpc_ws.websockets.connect",
                AsyncMock(return_value=socket),
            ),
            patch(
                "app.checks.jsonrpc_ws.time",
                SimpleNamespace(
                    monotonic=Mock(side_effect=[0, 0, 0, 6, 6]),
                    time=lambda: 1_000,
                ),
            ),
            patch(
                "app.checks.jsonrpc_ws._get_block_time_via_http",
                AsyncMock(return_value=999),
            ),
        ):
            result = await check_jsonrpc_ws(
                "wss://example.test", "token", "https://example.test"
            )

        self.assertEqual(
            socket.sent[0]["params"][1]["maxSupportedTransactionVersion"], 1
        )
        self.assertEqual(socket.sent[0]["params"][1]["transactionDetails"], "none")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["blocks_received"], 1)
        self.assertEqual(result["latest_slot"], 100)
        self.assertEqual(result["block_height"], 90)
        self.assertEqual(socket.sent[-1]["method"], "blockUnsubscribe")
        self.assertTrue(socket.closed)

    async def test_notification_errors_fail_and_unsubscribe(self):
        for error in ({"UnsupportedTransactionVersion": 1}, "BlockStoreError"):
            with self.subTest(error=error):
                socket = FakeSocket({"slot": 100, "block": None, "err": error})
                with (
                    patch(
                        "app.checks.jsonrpc_ws.websockets.connect",
                        AsyncMock(return_value=socket),
                    ),
                    patch(
                        "app.checks.jsonrpc_ws.time",
                        SimpleNamespace(monotonic=lambda: 0),
                    ),
                ):
                    with self.assertRaisesRegex(
                        RuntimeError, "blockSubscribe notification"
                    ):
                        await check_jsonrpc_ws(
                            "wss://example.test", "token", "https://example.test"
                        )
                self.assertEqual(socket.sent[-1]["method"], "blockUnsubscribe")
                self.assertTrue(socket.closed)

    async def test_missing_block_is_not_a_successful_notification(self):
        socket = FakeSocket({"slot": 100, "block": None, "err": None})
        with (
            patch(
                "app.checks.jsonrpc_ws.websockets.connect",
                AsyncMock(return_value=socket),
            ),
            patch("app.checks.jsonrpc_ws.time", SimpleNamespace(monotonic=lambda: 0)),
        ):
            with self.assertRaisesRegex(RuntimeError, "missing block"):
                await check_jsonrpc_ws(
                    "wss://example.test", "token", "https://example.test"
                )
        self.assertTrue(socket.closed)
