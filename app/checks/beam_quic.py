import asyncio
import os


async def check_beam_quic(endpoint: str, token: str) -> dict:
    env = os.environ.copy()
    env["BEAM_QUIC_API_KEY"] = token
    process = await asyncio.create_subprocess_exec(
        "beam-quic-check",
        endpoint,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        stdout, stderr = await process.communicate()
    except BaseException:
        if process.returncode is None:
            process.kill()
            await process.wait()
        raise

    if process.returncode != 0:
        message = stderr.decode(errors="replace").strip() or "Beam QUIC handshake failed"
        raise RuntimeError(message)

    try:
        handshake_ms = float(stdout.decode().strip())
    except ValueError as error:
        raise RuntimeError("Beam QUIC checker returned an invalid response") from error

    return {"status": "ok", "handshake_ms": round(handshake_ms, 2)}
