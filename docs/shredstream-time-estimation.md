# Shredstream Time Estimation

## Background

Solana shreds/entries contain no built-in wall-clock timestamps. Each entry only has:

- **`num_hashes`** (u64) — number of PoH ticks since the previous entry
- **`hash`** ([u8; 32]) — the resulting PoH hash
- **`transactions`** (Vec\<VersionedTransaction\>) — included transactions

Timestamps exist only at the **block level**, set by the leader validator when producing the block.

## Where the slot number comes from

The slot number is provided by the **gRPC message envelope**, not from the entry data itself:

```proto
message SubscribeEntriesResponse {
  uint64 slot = 1;
  bytes entries = 2;  // bincode-serialized Vec<Entry>
}
```

The `entries` blob is raw bincode bytes (num_hashes, hash, transactions) — no slot, no timestamp.

## `getBlockTime` RPC method

Despite its name, `getBlockTime` operates on **slot numbers**, not block heights. It returns the estimated production time for the block at that slot.

Caveats:
- Only works for slots with a **confirmed or finalized** block
- Returns `null` for skipped slots (no block produced)
- Does **not** work for in-progress (unfinalized) slots

Since shredstream delivers entries for slots still being built, we cannot call `getBlockTime` on the shredstream slot directly.

## Estimation approach

To estimate shredstream freshness, we use a **reference slot extrapolation**:

1. Call `getSlot(commitment: "confirmed")` to get the latest confirmed slot
2. Call `getBlockTime(ref_slot)` to get its wall-clock timestamp
3. Compute the slot difference: `slot_diff = last_shredstream_slot - ref_slot`
4. Extrapolate: `estimated_time = ref_time + slot_diff * 0.4` (Solana slots are ~400ms apart)
5. Compute age: `age_seconds = now - estimated_time`

This works because the confirmed slot *just* got confirmed, so its timestamp is very close to "now" from the chain's perspective. In practice, shredstream is typically 1–2 slots ahead of confirmed, resulting in an age of ~1s.

## Example

```
ref_slot       = 407466974  (confirmed)
ref_time       = 1773930140 (from getBlockTime)
last_slot      = 407466975  (from shredstream)
slot_diff      = 1
estimated_time = 1773930140 + 1 * 0.4 = 1773930140.4
now            = 1773930141
age_seconds    = ~1s
```
