import asyncio
import json

import grpc
import httpx
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.checks.jsonrpc_http import check_jsonrpc_http
from app.checks.jsonrpc_ws import check_jsonrpc_ws
from app.checks.shredstream import check_shredstream
from app.checks.yellowstone import check_yellowstone
from app.endpoints import resolve_endpoints


def format_error(e: Exception) -> str:
    if isinstance(e, grpc.aio.AioRpcError):
        code = e.code().name
        message = e.details() or str(e)
        return f"gRPC {code}: {message}"
    if isinstance(e, httpx.HTTPStatusError):
        return f"HTTP {e.response.status_code}: {e.response.reason_phrase}"
    return str(e)

app = FastAPI(title="RPCFast Endpoint Checker")


class CheckRequest(BaseModel):
    token: str
    endpoint_type: str = "saas"
    client_id: str | None = None


@app.post("/api/check")
async def run_checks(req: CheckRequest):
    endpoints = resolve_endpoints(req.endpoint_type, req.client_id)

    async def event_generator():
        checks = [
            ("jsonrpc_http", check_jsonrpc_http, [endpoints.jsonrpc_http, req.token]),
            ("yellowstone_grpc", check_yellowstone, [endpoints.yellowstone_grpc, req.token, endpoints.jsonrpc_http]),
            ("shredstream_grpc", check_shredstream, [endpoints.shredstream_grpc, req.token, endpoints.jsonrpc_http]),
            ("jsonrpc_ws", check_jsonrpc_ws, [endpoints.jsonrpc_ws, req.token, endpoints.jsonrpc_http]),
        ]

        # Emit all "running" statuses first
        for name, _, args in checks:
            yield {
                "event": "status",
                "data": json.dumps({"check": name, "status": "running", "endpoint": args[0]}),
            }

        # Run all checks in parallel
        async def run_check(name, check_fn, args):
            try:
                result = await asyncio.wait_for(check_fn(*args), timeout=30.0)
                return name, result
            except asyncio.TimeoutError:
                return name, {"status": "error", "error": "Timeout (30s)"}
            except Exception as e:
                return name, {"status": "error", "error": format_error(e)}

        tasks = [run_check(name, fn, args) for name, fn, args in checks]
        for coro in asyncio.as_completed(tasks):
            name, result = await coro
            yield {
                "event": "result",
                "data": json.dumps({"check": name, **result}),
            }

        yield {"event": "done", "data": "{}"}

    return EventSourceResponse(event_generator())


@app.get("/health")
async def health():
    return {"status": "ok"}


app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
async def root():
    return FileResponse("app/static/index.html")
