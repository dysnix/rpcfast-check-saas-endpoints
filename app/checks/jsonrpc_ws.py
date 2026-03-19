import asyncio
import json
import time

import httpx
import websockets


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


async def check_jsonrpc_ws(endpoint: str, token: str, http_url: str) -> dict:
    headers = {"x-token": token}

    try:
        ws = await websockets.connect(endpoint, additional_headers=headers)
    except websockets.exceptions.InvalidStatusCode as e:
        if e.status_code == 401:
            raise RuntimeError("WebSocket HTTP 401 Unauthorized") from None
        if e.status_code == 403:
            raise RuntimeError("WebSocket HTTP 403 Forbidden") from None
        raise RuntimeError(f"WebSocket connection failed: HTTP {e.status_code}") from None

    async with ws:
        # Use "allWithVotes" filter — "all" is not supported on SaaS endpoints
        subscribe_msg = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "blockSubscribe",
            "params": [
                {"mentionsAccountOrProgram": "Vote111111111111111111111111111111111111111"},
                {"commitment": "confirmed", "transactionDetails": "none", "rewards": False},
            ],
        })
        await ws.send(subscribe_msg)

        confirm = json.loads(await ws.recv())
        if "error" in confirm:
            raise RuntimeError(f"blockSubscribe: {confirm['error']}")

        subscription_id = confirm.get("result")
        blocks = []
        start = time.monotonic()

        try:
            while time.monotonic() - start < 5.0:
                remaining = 5.0 - (time.monotonic() - start)
                if remaining <= 0:
                    break
                raw = await asyncio.wait_for(ws.recv(), timeout=remaining + 1.0)
                msg = json.loads(raw)
                if "params" in msg and "result" in msg["params"]:
                    value = msg["params"]["result"]["value"]
                    blocks.append({
                        "slot": value.get("slot"),
                        "block_height": value.get("block", {}).get("blockHeight"),
                    })
        except asyncio.TimeoutError:
            pass

        # Unsubscribe (best effort)
        if subscription_id is not None:
            try:
                unsub = json.dumps({
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "blockUnsubscribe",
                    "params": [subscription_id],
                })
                await ws.send(unsub)
            except Exception:
                pass

    if not blocks:
        return {
            "status": "warning",
            "message": "No blocks received in 5 seconds",
            "blocks_received": 0,
        }

    latest = blocks[-1]
    latest_slot = latest["slot"]
    block_height = latest.get("block_height")
    elapsed = round(time.monotonic() - start, 2)

    # Validate latest block timestamp via HTTP
    block_time = await _get_block_time_via_http(http_url, token, latest_slot)
    now = int(time.time())
    age_seconds = now - block_time

    result = {
        "status": "ok",
        "blocks_received": len(blocks),
        "latest_slot": latest_slot,
        "block_time": block_time,
        "age_seconds": age_seconds,
        "elapsed_seconds": elapsed,
    }
    if block_height is not None:
        result["block_height"] = block_height
    return result
