import asyncio
import unittest
from unittest.mock import patch

from app.checks.grpc_stream import consume_for_duration
from app.checks.shredstream import check_shredstream


class BlockingCall:
    def __init__(self):
        self.cancelled = False
        self.read_started = asyncio.Event()

    def __aiter__(self):
        return self

    async def __anext__(self):
        self.read_started.set()
        await asyncio.Future()

    def cancel(self):
        self.cancelled = True


class StreamLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_is_cancelled_after_duration(self):
        call = BlockingCall()

        elapsed = await consume_for_duration(call, 0.01, lambda _: None)

        self.assertTrue(call.cancelled)
        self.assertGreaterEqual(elapsed, 0.01)

    async def test_shredstream_closes_call_and_channel_after_stream_ends(self):
        class EmptyCall:
            def __init__(self):
                self.cancelled = False

            def __aiter__(self):
                return self

            async def __anext__(self):
                raise StopAsyncIteration

            def cancel(self):
                self.cancelled = True

        class Channel:
            def __init__(self):
                self.closed = False

            async def close(self):
                self.closed = True

        call = EmptyCall()
        channel = Channel()
        stub = type(
            "Stub",
            (),
            {"SubscribeEntries": lambda self, request, metadata: call},
        )()

        with (
            patch("app.checks.shredstream.grpc.aio.secure_channel", return_value=channel),
            patch(
                "app.checks.shredstream.shredstream_pb2_grpc.ShredstreamProxyStub",
                return_value=stub,
            ),
        ):
            await check_shredstream("endpoint", "token", "http", "http-token")

        self.assertTrue(call.cancelled)
        self.assertTrue(channel.closed)

    async def test_stream_is_cancelled_when_parent_task_is_cancelled(self):
        call = BlockingCall()
        task = asyncio.create_task(consume_for_duration(call, 10, lambda _: None))
        await call.read_started.wait()

        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

        self.assertTrue(call.cancelled)
