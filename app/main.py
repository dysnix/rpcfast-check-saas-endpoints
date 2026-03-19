import asyncio
import json
import re

import grpc
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

# Only allow alphanumeric and hyphens in client_id to prevent SSRF
CLIENT_ID_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
VALID_ENDPOINT_TYPES = {"saas", "dedicated"}

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
    http_token: str
    endpoint_type: str = "saas"
    client_id: str | None = None
    yellowstone_token: str | None = None
    shredstream_token: str | None = None


@app.post("/api/check")
async def run_checks(req: CheckRequest):
    # Validate endpoint_type
    if req.endpoint_type not in VALID_ENDPOINT_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid endpoint_type: must be one of {VALID_ENDPOINT_TYPES}")

    # Validate client_id to prevent SSRF via URL injection
    if req.endpoint_type == "dedicated":
        if not req.client_id:
            raise HTTPException(status_code=400, detail="client_id is required for dedicated endpoints")
        if not CLIENT_ID_PATTERN.match(req.client_id) or len(req.client_id) > 64:
            raise HTTPException(status_code=400, detail="client_id must be lowercase alphanumeric with optional hyphens (max 64 chars)")

    endpoints = resolve_endpoints(req.endpoint_type, req.client_id)

    # Resolve per-service tokens:
    # Dedicated: single http_token for all services
    # SaaS: http_token for HTTP+WS, separate optional tokens for gRPC
    http_token = req.http_token
    if req.endpoint_type == "dedicated":
        ys_token = req.http_token
        ss_token = req.http_token
    else:
        ys_token = req.yellowstone_token
        ss_token = req.shredstream_token

    async def event_generator():
        checks = [
            ("jsonrpc_http", check_jsonrpc_http, [endpoints.jsonrpc_http, http_token]),
            ("jsonrpc_ws", check_jsonrpc_ws, [endpoints.jsonrpc_ws, http_token, endpoints.jsonrpc_http]),
        ]
        if ys_token:
            checks.append(("yellowstone_grpc", check_yellowstone, [endpoints.yellowstone_grpc, ys_token, endpoints.jsonrpc_http, http_token]))
        if ss_token:
            checks.append(("shredstream_grpc", check_shredstream, [endpoints.shredstream_grpc, ss_token, endpoints.jsonrpc_http, http_token]))

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
