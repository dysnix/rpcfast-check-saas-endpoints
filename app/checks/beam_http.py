import time

import httpx


async def check_beam_http(endpoint: str, token: str) -> dict:
    started = time.monotonic()
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            endpoint,
            headers={"x-token": token, "Content-Type": "application/json"},
            json={"jsonrpc": "2.0", "id": 1, "method": "getHealth"},
        )
        response.raise_for_status()
        data = response.json()

    if "error" in data:
        raise RuntimeError(f"getHealth: {data['error']}")
    if data.get("result") != "ok":
        raise RuntimeError(f"getHealth: unexpected result {data.get('result')!r}")

    return {
        "status": "ok",
        "result": data["result"],
        "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
    }
