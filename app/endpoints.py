from dataclasses import dataclass


@dataclass
class EndpointSet:
    jsonrpc_http: str
    jsonrpc_ws: str
    yellowstone_grpc: str
    shredstream_grpc: str


def resolve_endpoints(client_id: str) -> EndpointSet:
    if client_id == "saas":
        return EndpointSet(
            jsonrpc_http="https://solana-rpc.rpcfast.net",
            jsonrpc_ws="wss://solana-rpc.rpcfast.net/ws",
            yellowstone_grpc="solana-yellowstone-grpc.rpcfast.net:443",
            shredstream_grpc="solana-shredstream-grpc.rpcfast.net:443",
        )
    return EndpointSet(
        jsonrpc_http=f"https://sol-rpc-{client_id}.rpcfast.net",
        jsonrpc_ws=f"wss://sol-rpc-{client_id}.rpcfast.net/ws",
        yellowstone_grpc=f"sol-yellowstone-{client_id}.rpcfast.net:443",
        shredstream_grpc=f"sol-shredstream-{client_id}.rpcfast.net:443",
    )
