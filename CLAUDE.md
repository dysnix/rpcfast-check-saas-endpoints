# CLAUDE.md

## Project Overview

RPCFast Solana Endpoint Checker — a FastAPI web app that validates RPCFast Solana RPC endpoints on demand. It checks 4 endpoint types in parallel and streams results to a web UI via SSE.

## Tech Stack

- **Python 3.13** with FastAPI + uvicorn
- **gRPC** (grpcio/grpcio-tools) for Yellowstone Geyser and Shredstream
- **httpx** for async HTTP JSON-RPC calls
- **websockets** for JSON-RPC WebSocket subscriptions
- **sse-starlette** for Server-Sent Events streaming
- **uv** for Python dependency management
- **Docker** (multi-stage build with uv)
- **Helm** (dysnix/app chart) for Kubernetes deployment

## Project Structure

```
app/
├── main.py                 # FastAPI entry point, SSE streaming, parallel check orchestration
├── endpoints.py            # Resolves client_id ("saas" or custom) to endpoint URLs
├── checks/
│   ├── jsonrpc_http.py     # HTTP: getBlockHeight + getSlot + getBlockTime
│   ├── jsonrpc_ws.py       # WS: blockSubscribe (confirmed) for 5s
│   ├── yellowstone.py      # gRPC: GetSlot + GetBlockHeight (processed)
│   └── shredstream.py      # gRPC: SubscribeEntries for 5s, bincode entry decoder
├── static/
│   └── index.html          # Single-page frontend (dark theme, SSE, grade cards)
└── proto_compiled/         # Auto-generated at Docker build time (gitignored)
proto/
├── geyser.proto            # Yellowstone Geyser service
├── solana-storage.proto    # Solana block/tx structures
├── shredstream.proto       # Shredstream proxy service
└── shared.proto            # Shared message types
scripts/
└── compile_protos.sh       # Proto compilation + sed import fixups
helm/
└── values.yaml             # K8s deployment config (dysnix/app chart)
docs/
└── shredstream-time-estimation.md  # How shredstream freshness is estimated
```

## Key Concepts

### Endpoint Resolution
- `saas` → `solana-rpc.rpcfast.net`, `solana-yellowstone-grpc.rpcfast.net:443`, etc.
- Custom client (e.g. `sultan`) → `sol-rpc-sultan.rpcfast.net`, etc.
- Frontend sends only `x-token` + `client_id`; backend resolves actual URLs.

### Solana Commitment Levels
- **processed** — latest, used for HTTP and Yellowstone checks
- **confirmed** — required minimum for WS `blockSubscribe`
- **finalized** — ~32 slots behind, too stale for freshness checks

### Shredstream Entry Decoding
- Entries are bincode-serialized `Vec<Entry>` (u64 length prefix + entries)
- Each entry: `num_hashes` (u64) + `hash` ([u8;32]) + `transactions` (Vec<VersionedTx>)
- **No wall-clock timestamps** in shreds — time is estimated via reference slot extrapolation
- See `docs/shredstream-time-estimation.md` for details

### Health Grading
- 🟢 Green: < 10s block age
- 🟡 Yellow: 10–30s
- 🟠 Orange: 30–60s
- 🔴 Red: > 60s

## Build & Run

```bash
# Build Docker image (compiles protos at build time)
docker build -f Dockerfile.uv -t rpcfast-check .

# Run locally
docker run -d --name rpcfast-check -p 8000:8000 rpcfast-check

# Health check
curl http://localhost:8000/health
```

## Proto Compilation

Protos are compiled **only at Docker build time** via `scripts/compile_protos.sh`. The script runs `python -m grpc_tools.protoc` and applies sed fixups for relative Python imports. No locally compiled proto files are committed.

## CI/CD

GitHub Actions (`.github/workflows/docker-build-push.yml`) builds multi-platform images (amd64 + arm64) and pushes to `ghcr.io/dysnix/rpcfast-check-saas-endpoints`.

## Common Pitfalls

- `getBlockTime` works on **slots** (not block heights), only for confirmed/finalized slots
- `blockSubscribe` requires minimum `confirmed` commitment — `processed` will error
- Proto import fixups use single underscores (`solana_storage_pb2`), not double
- The venv must be on PATH (`ENV PATH="/app/.venv/bin:$PATH"`) before proto compilation in Docker
