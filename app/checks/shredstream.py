import struct
import time
from io import BytesIO

import grpc
import httpx

from app.proto_compiled import shredstream_pb2, shredstream_pb2_grpc


def decode_entries_summary(raw: bytes) -> dict:
    """Decode bincode-serialized Vec<Entry> header from shredstream.

    The format is:
      - u64: number of entries in the vec
      - For each entry:
        - num_hashes: u64 (8 bytes LE)
        - hash: [u8; 32] (32 bytes)
        - transactions: Vec<VersionedTransaction> (u64 length prefix + variable tx data)

    We only read the vec length prefix and then parse entry headers sequentially.
    Since transactions are variable-length and complex to skip, we parse what we
    can and stop when we hit the first transaction boundary.
    """
    if len(raw) < 8:
        return {"entry_count": 0, "total_transactions": 0}

    reader = BytesIO(raw)

    # Vec<Entry> length prefix
    vec_len = struct.unpack("<Q", reader.read(8))[0]

    # Sanity check — vec_len shouldn't be absurdly large
    if vec_len > 10000:
        return {"entry_count": 0, "total_transactions": 0, "parse_error": "vec_len too large"}

    entry_count = 0
    total_transactions = 0

    for _ in range(vec_len):
        # num_hashes: u64
        chunk = reader.read(8)
        if len(chunk) < 8:
            break
        num_hashes = struct.unpack("<Q", chunk)[0]

        # hash: [u8; 32]
        hash_bytes = reader.read(32)
        if len(hash_bytes) < 32:
            break

        # transactions: Vec<VersionedTransaction> — u64 length prefix
        chunk = reader.read(8)
        if len(chunk) < 8:
            break
        num_txs = struct.unpack("<Q", chunk)[0]

        # Sanity check
        if num_txs > 100000:
            break

        entry_count += 1
        total_transactions += num_txs

        # Skip transaction bytes — we can't easily know the exact size,
        # so consume remaining bytes for this entry by reading each tx
        skipped_ok = True
        for _ in range(num_txs):
            # VersionedTransaction in bincode:
            # signatures: Vec<Signature> = u64 len + N * 64 bytes
            sig_chunk = reader.read(8)
            if len(sig_chunk) < 8:
                skipped_ok = False
                break
            num_sigs = struct.unpack("<Q", sig_chunk)[0]
            if num_sigs > 256:
                skipped_ok = False
                break
            if reader.read(int(num_sigs * 64)) is None:
                skipped_ok = False
                break

            # Message: first byte determines type
            prefix = reader.read(1)
            if len(prefix) < 1:
                skipped_ok = False
                break

            is_versioned = prefix[0] >= 0x80

            # MessageHeader: 3 bytes
            hdr = reader.read(3)
            if len(hdr) < 3:
                skipped_ok = False
                break

            # account_keys: Vec<Pubkey> = u64 len + N * 32 bytes
            ak_chunk = reader.read(8)
            if len(ak_chunk) < 8:
                skipped_ok = False
                break
            num_ak = struct.unpack("<Q", ak_chunk)[0]
            if num_ak > 256:
                skipped_ok = False
                break
            reader.read(int(num_ak * 32))

            # recent_blockhash: 32 bytes
            reader.read(32)

            # instructions: Vec<CompiledInstruction>
            ic_chunk = reader.read(8)
            if len(ic_chunk) < 8:
                skipped_ok = False
                break
            num_ix = struct.unpack("<Q", ic_chunk)[0]
            if num_ix > 1000:
                skipped_ok = False
                break

            for _ in range(num_ix):
                reader.read(1)  # program_id_index
                al = reader.read(8)
                if len(al) < 8:
                    skipped_ok = False
                    break
                acc_len = struct.unpack("<Q", al)[0]
                reader.read(int(acc_len))
                dl = reader.read(8)
                if len(dl) < 8:
                    skipped_ok = False
                    break
                data_len = struct.unpack("<Q", dl)[0]
                reader.read(int(data_len))

            if not skipped_ok:
                break

            # address_table_lookups for versioned messages
            if is_versioned:
                atl_chunk = reader.read(8)
                if len(atl_chunk) < 8:
                    skipped_ok = False
                    break
                num_atl = struct.unpack("<Q", atl_chunk)[0]
                if num_atl > 256:
                    skipped_ok = False
                    break
                for _ in range(num_atl):
                    reader.read(32)  # account_key
                    wl = reader.read(8)
                    if len(wl) < 8:
                        skipped_ok = False
                        break
                    reader.read(struct.unpack("<Q", wl)[0])
                    rl = reader.read(8)
                    if len(rl) < 8:
                        skipped_ok = False
                        break
                    reader.read(struct.unpack("<Q", rl)[0])

            if not skipped_ok:
                break

        if not skipped_ok:
            break

    return {"entry_count": entry_count, "total_transactions": total_transactions}


async def check_shredstream(endpoint: str, token: str, http_url: str) -> dict:
    metadata = [("x-token", token)]
    channel = grpc.aio.secure_channel(
        endpoint,
        grpc.ssl_channel_credentials(),
    )
    try:
        stub = shredstream_pb2_grpc.ShredstreamProxyStub(channel)
        request = shredstream_pb2.SubscribeEntriesRequest()

        total_bytes = 0
        entry_count = 0
        total_transactions = 0
        total_solana_entries = 0
        slots_seen = set()
        last_slot = 0
        decode_errors = 0
        start_time = time.monotonic()
        duration = 5.0  # seconds

        async for entry in stub.SubscribeEntries(request, metadata=metadata):
            total_bytes += len(entry.entries)
            entry_count += 1
            last_slot = entry.slot
            slots_seen.add(entry.slot)

            # Try to decode the entry data
            try:
                summary = decode_entries_summary(entry.entries)
                total_solana_entries += summary["entry_count"]
                total_transactions += summary["total_transactions"]
            except Exception:
                decode_errors += 1

            if time.monotonic() - start_time >= duration:
                break

        elapsed = time.monotonic() - start_time
        speed_mbps = (total_bytes * 8) / (elapsed * 1_000_000) if elapsed > 0 else 0

        # Estimate shredstream freshness:
        # getBlockTime only works for finalized slots, but shredstream delivers
        # entries for slots still being built. So we get a confirmed slot + its
        # time from the RPC, then extrapolate using ~400ms per slot.
        block_time = None
        age_seconds = None
        ref_slot = None
        slot_diff = None
        if last_slot:
            try:
                headers = {"x-token": token, "Content-Type": "application/json"}
                async with httpx.AsyncClient(timeout=10.0) as client:
                    # Get a confirmed slot and its block time as reference
                    resp = await client.post(
                        http_url, headers=headers,
                        json={"jsonrpc": "2.0", "id": 1, "method": "getSlot",
                              "params": [{"commitment": "confirmed"}]},
                    )
                    ref_slot = resp.json().get("result")
                    if ref_slot:
                        resp2 = await client.post(
                            http_url, headers=headers,
                            json={"jsonrpc": "2.0", "id": 2, "method": "getBlockTime",
                                  "params": [ref_slot]},
                        )
                        ref_time = resp2.json().get("result")
                        if ref_time:
                            block_time = ref_time
                            slot_diff = last_slot - ref_slot
                            # Extrapolate: each slot is ~400ms
                            estimated_time = ref_time + slot_diff * 0.4
                            age_seconds = round(time.time() - estimated_time)
            except Exception:
                pass

        return {
            "status": "ok",
            "bytes_downloaded": total_bytes,
            "grpc_messages": entry_count,
            "solana_entries_decoded": total_solana_entries,
            "transactions_seen": total_transactions,
            "slots_seen": len(slots_seen),
            "last_slot": last_slot,
            "ref_slot": ref_slot,
            "slot_ahead": slot_diff,
            "block_time": block_time,
            "age_seconds": age_seconds,
            "decode_errors": decode_errors,
            "elapsed_seconds": round(elapsed, 2),
            "speed_mbps": round(speed_mbps, 2),
        }
    finally:
        await channel.close()
