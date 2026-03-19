import time

import grpc
import httpx

from app.proto_compiled import geyser_pb2, geyser_pb2_grpc


async def _get_block_time_via_http(http_url: str, token: str, slot: int) -> int:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            http_url,
            headers={"x-token": token, "Content-Type": "application/json"},
            json={"jsonrpc": "2.0", "id": 1, "method": "getBlockTime", "params": [slot]},
        )
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"getBlockTime: {data['error']}")
        return data["result"]


async def check_yellowstone(endpoint: str, token: str, http_url: str) -> dict:
    metadata = [("x-token", token)]
    channel = grpc.aio.secure_channel(
        endpoint,
        grpc.ssl_channel_credentials(),
    )
    try:
        stub = geyser_pb2_grpc.GeyserStub(channel)

        slot_resp = await stub.GetSlot(
            geyser_pb2.GetSlotRequest(commitment=geyser_pb2.PROCESSED), metadata=metadata
        )
        height_resp = await stub.GetBlockHeight(
            geyser_pb2.GetBlockHeightRequest(commitment=geyser_pb2.PROCESSED), metadata=metadata
        )

        slot = slot_resp.slot
        block_height = height_resp.block_height

        block_time = await _get_block_time_via_http(http_url, token, slot)
        now = int(time.time())
        age_seconds = now - block_time

        return {
            "status": "ok",
            "slot": slot,
            "block_height": block_height,
            "block_time": block_time,
            "age_seconds": age_seconds,
        }
    finally:
        await channel.close()
