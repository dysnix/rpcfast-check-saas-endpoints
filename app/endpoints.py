from dataclasses import dataclass


@dataclass
class EndpointSet:
    jsonrpc_http: str
    jsonrpc_ws: str
    yellowstone_grpc: str
    shredstream_grpc: str


def resolve_endpoints(endpoint_type: str, client_id: str | None = None) -> EndpointSet:
    if endpoint_type == "saas":
        return EndpointSet(
            jsonrpc_http="https://solana-rpc.rpcfast.com",
            jsonrpc_ws="wss://solana-rpc.rpcfast.com/ws",
            yellowstone_grpc="solana-yellowstone-grpc.rpcfast.com:443",
            shredstream_grpc="solana-shredstream-grpc.rpcfast.com:443",
        )
    # dedicated — requires client_id
    return EndpointSet(
        jsonrpc_http=f"https://sol-rpc-{client_id}.rpcfast.net",
        jsonrpc_ws=f"wss://sol-rpc-{client_id}.rpcfast.net/ws",
        yellowstone_grpc=f"sol-yellowstone-{client_id}.rpcfast.net:443",
        shredstream_grpc=f"sol-shredstream-{client_id}.rpcfast.net:443",
    )
