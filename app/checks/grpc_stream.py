import asyncio
import time
from collections.abc import Callable
from typing import Any


async def consume_for_duration(
    call: Any,
    duration: float,
    consume: Callable[[Any], None],
) -> float:
    """Consume a gRPC stream for a bounded time and always cancel the RPC."""
    started = time.monotonic()
    try:
        try:
            async with asyncio.timeout(duration):
                async for message in call:
                    consume(message)
        except TimeoutError:
            pass
    finally:
        call.cancel()

    return time.monotonic() - started
