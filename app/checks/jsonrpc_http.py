import time

import httpx


def _check_http_response(resp: httpx.Response, method: str):
    if resp.status_code == 401:
        raise RuntimeError(f"HTTP 401 Unauthorized")
    if resp.status_code == 403:
        raise RuntimeError(f"HTTP 403 Forbidden")
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"{method}: {data['error']}")
    return data["result"]


async def check_jsonrpc_http(endpoint: str, token: str) -> dict:
    headers = {"x-token": token, "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            endpoint,
            headers=headers,
            json={"jsonrpc": "2.0", "id": 1, "method": "getBlockHeight", "params": [{"commitment": "processed"}]},
        )
        block_height = _check_http_response(resp, "getBlockHeight")

        resp2 = await client.post(
            endpoint,
            headers=headers,
            json={"jsonrpc": "2.0", "id": 2, "method": "getSlot", "params": [{"commitment": "processed"}]},
        )
        slot = _check_http_response(resp2, "getSlot")

        resp3 = await client.post(
            endpoint,
            headers=headers,
            json={"jsonrpc": "2.0", "id": 3, "method": "getBlockTime", "params": [slot]},
        )
        block_time = _check_http_response(resp3, "getBlockTime")

        now = int(time.time())
        age_seconds = now - block_time

        return {
            "status": "ok",
            "block_height": block_height,
            "slot": slot,
            "block_time": block_time,
            "age_seconds": age_seconds,
        }
