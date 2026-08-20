from dataclasses import dataclass


@dataclass
class EndpointSet:
    jsonrpc_http: str
    jsonrpc_ws: str
    yellowstone_grpc: str
    shredstream_grpc: str
    aperture_txstream_grpc: str
    beam_http: str
    beam_quic: str


def resolve_endpoints(endpoint_type: str, client_id: str | None = None) -> EndpointSet:
    if endpoint_type == "saas":
        return EndpointSet(
            jsonrpc_http="https://solana-rpc.rpcfast.com",
            jsonrpc_ws="wss://solana-rpc.rpcfast.com/ws",
            yellowstone_grpc="solana-yellowstone-grpc.rpcfast.com:443",
            shredstream_grpc="solana-shredstream-grpc.rpcfast.com:443",
            aperture_txstream_grpc="aperture-txstream.rpcfast.com:443",
            beam_http="https://beam.rpcfast.com",
            beam_quic="beam.rpcfast.com:9900",
        )
    if endpoint_type == "saas-devnet":
        return EndpointSet(
            jsonrpc_http="https://sol-devnet-rpc.rpcfast.com",
            jsonrpc_ws="wss://sol-devnet-rpc.rpcfast.com/ws",
            yellowstone_grpc="sol-devnet-yellowstone-grpc.rpcfast.com:443",
            shredstream_grpc="",
            aperture_txstream_grpc="",
            beam_http="",
            beam_quic="",
        )
    # dedicated — requires client_id
    return EndpointSet(
        jsonrpc_http=f"https://sol-rpc-{client_id}.rpcfast.net",
        jsonrpc_ws=f"wss://sol-rpc-{client_id}.rpcfast.net/ws",
        yellowstone_grpc=f"sol-yellowstone-{client_id}.rpcfast.net:443",
        shredstream_grpc=f"sol-shredstream-{client_id}.rpcfast.net:443",
        aperture_txstream_grpc="",
        beam_http="",
        beam_quic="",
    )
