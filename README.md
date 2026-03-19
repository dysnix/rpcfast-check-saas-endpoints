# RPCFast Solana Endpoint Checker

Web app to check RPCFast Solana RPC endpoints on demand. Runs 4 checks in parallel and streams results via SSE. 100% vibe-coded.

## Checks

| Check | Protocol | What it does |
|-------|----------|-------------|
| JSON-RPC HTTP | HTTP | `getBlockHeight`, `getSlot`, `getBlockTime` |
| JSON-RPC WebSocket | WS | `blockSubscribe` for 5s |
| Yellowstone gRPC | gRPC | `GetSlot`, `GetBlockHeight` via Geyser |
| Shredstream gRPC | gRPC | `SubscribeEntries` for 5s, decodes entries |

## Build & Run

```bash
docker build -f Dockerfile.uv -t rpcfast-check .
docker run -d -p 8000:8000 rpcfast-check
```

Open http://localhost:8000, enter your x-token / API key, select endpoint type, and click "Check Endpoints".

## Deploy (Kubernetes)

Uses [dysnix/app](https://github.com/dysnix/charts/tree/main/dysnix/app) Helm chart:

```bash
helm upgrade --install rpcfast-check dysnix/app -f helm/values.yaml
```

## Proto Sources

| File | Source |
|------|--------|
| `geyser.proto` | [jito-labs/yellowstone-grpc](https://github.com/rpcpool/yellowstone-grpc/blob/master/yellowstone-grpc-proto/proto/geyser.proto) |
| `solana-storage.proto` | [jito-labs/yellowstone-grpc](https://github.com/rpcpool/yellowstone-grpc/blob/master/yellowstone-grpc-proto/proto/solana-storage.proto) |
| `shredstream.proto` | [jito-labs/mev-protos](https://github.com/jito-labs/mev-protos/blob/master/protos/shredstream.proto) |
| `shared.proto` | [jito-labs/mev-protos](https://github.com/jito-labs/mev-protos/blob/master/protos/shared.proto) |

Protos are compiled at Docker build time via `scripts/compile_protos.sh`.
