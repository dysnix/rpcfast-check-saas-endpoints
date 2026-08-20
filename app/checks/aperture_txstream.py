import time

import base58
import grpc

from app.checks.grpc_stream import consume_for_duration
from app.proto_compiled import txstream_pb2, txstream_pb2_grpc

SIMULATION_PLAN_DENIAL = "Real-time simulation is not available for your plan"
TXSTREAM_ACCOUNT_INCLUDE = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
OPERATIONAL_SIMULATION_STATUSES = {
    "SIMULATION_STATUS_SUCCEEDED",
    "SIMULATION_STATUS_FAILED",
    "SIMULATION_STATUS_INVALID_TRANSACTION",
    "SIMULATION_STATUS_BANK_NOT_AVAILABLE",
}


def classify_simulation_health(
    transaction_count: int,
    simulations_seen: int,
    simulation_statuses: dict[str, int],
) -> tuple[str, str | None, str | None, int]:
    operational_results = sum(
        count
        for status, count in simulation_statuses.items()
        if status in OPERATIONAL_SIMULATION_STATUSES
    )
    service_errors = simulations_seen - operational_results

    if not transaction_count:
        return (
            "warning",
            "no_simulated_transactions",
            "No simulated transactions received in 5 seconds",
            service_errors,
        )
    if simulations_seen != transaction_count:
        return (
            "error",
            "missing_simulation_results",
            "TxStream returned transactions without simulation results",
            service_errors,
        )
    if operational_results == 0:
        return (
            "error",
            "simulation_unhealthy",
            "All simulation results reported service-level failures",
            service_errors,
        )
    if service_errors:
        return (
            "warning",
            "simulation_partially_unhealthy",
            "Some simulation results reported service-level failures",
            service_errors,
        )
    return "ok", None, None, 0


def is_simulation_plan_denial(error: grpc.aio.AioRpcError) -> bool:
    return (
        error.code() == grpc.StatusCode.PERMISSION_DENIED
        and error.details() == SIMULATION_PLAN_DENIAL
    )


def build_subscribe_request(include_simulation: bool):
    return txstream_pb2.SubscribeTransactionsRequest(
        vote=txstream_pb2.VOTE_FILTER_NON_VOTE_ONLY,
        account_include=[base58.b58decode(TXSTREAM_ACCOUNT_INCLUDE)],
        signatures_only=True,
        include_simulation=include_simulation,
    )


async def _check_aperture_txstream(
    endpoint: str,
    token: str,
    *,
    include_simulation: bool,
) -> dict:
    channel = grpc.aio.secure_channel(endpoint, grpc.ssl_channel_credentials())
    try:
        stub = txstream_pb2_grpc.ApertureStub(channel)
        request = build_subscribe_request(include_simulation)
        call = stub.SubscribeTransactions(request, metadata=[("x-token", token)])

        transaction_count = 0
        signature_count = 0
        slots_seen = set()
        last_slot = 0
        latest_index = None
        latest_created_at = 0
        simulations_seen = 0
        simulation_statuses = {}

        def consume_transaction(transaction):
            nonlocal transaction_count, signature_count, last_slot
            nonlocal latest_index, latest_created_at
            nonlocal simulations_seen
            transaction_count += 1
            signature_count += len(transaction.signatures)
            slots_seen.add(transaction.slot)
            last_slot = transaction.slot
            latest_index = transaction.index
            latest_created_at = transaction.created_at_unix_nanos
            if include_simulation and transaction.HasField("simulation"):
                simulations_seen += 1
                status_name = txstream_pb2.SimulationStatus.Name(
                    transaction.simulation.status
                )
                simulation_statuses[status_name] = (
                    simulation_statuses.get(status_name, 0) + 1
                )

        elapsed = await consume_for_duration(call, 5.0, consume_transaction)
        age_seconds = None
        if latest_created_at:
            age_seconds = round(time.time() - latest_created_at / 1_000_000_000, 3)

        status = "ok" if transaction_count else "warning"
        result = {
            "status": status,
            "transactions_seen": transaction_count,
            "signatures_seen": signature_count,
            "slots_seen": len(slots_seen),
            "last_slot": last_slot,
            "latest_index": latest_index,
            "age_seconds": age_seconds,
            "elapsed_seconds": round(elapsed, 2),
            "transactions_per_second": round(transaction_count / elapsed, 2)
            if elapsed
            else 0,
        }
        if include_simulation:
            result["simulations_seen"] = simulations_seen
            result["simulation_statuses"] = simulation_statuses
            health_status, reason, message, service_errors = (
                classify_simulation_health(
                    transaction_count,
                    simulations_seen,
                    simulation_statuses,
                )
            )
            result["simulation_service_errors"] = service_errors
            result["status"] = health_status
            if reason:
                result["reason"] = reason
            if message:
                result["message"] = message

        if not include_simulation and not transaction_count:
            result["reason"] = "no_transactions"
            result["message"] = "No transactions received in 5 seconds"
        return result
    finally:
        await channel.close()


async def check_aperture_txstream(endpoint: str, token: str) -> dict:
    return await _check_aperture_txstream(
        endpoint,
        token,
        include_simulation=False,
    )


async def check_aperture_simulation(endpoint: str, token: str) -> dict:
    try:
        return await _check_aperture_txstream(
            endpoint,
            token,
            include_simulation=True,
        )
    except grpc.aio.AioRpcError as error:
        if is_simulation_plan_denial(error):
            return {
                "status": "warning",
                "reason": "simulation_not_in_plan",
                "grpc_code": error.code().name,
                "message": SIMULATION_PLAN_DENIAL,
            }
        raise
