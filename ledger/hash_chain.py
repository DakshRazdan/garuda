"""
Hash-chain utilities — tamper-evidence for the batch ledger.

This is deliberately NOT a blockchain: no consensus, no distributed
nodes, no mining. It's an append-only hash chain (each row's hash is
derived from its own data plus the previous row's hash) — the same
integrity idea Git commits and audit logs use. Cheap, explainable, and
enough to prove "this ledger wasn't quietly edited after the fact"
when a judge or regulator asks.
"""

import hashlib
from typing import List, Optional, Tuple


def compute_row_hash(farm_id: str, weight_kg: float, crop_type: str,
                      timestamp_iso: str, prev_hash: str) -> str:
    """
    Deterministic hash for one batch row. Changing any field, or the
    prev_hash it points to, changes this value — which breaks every
    hash after it in the chain, making tampering detectable.
    """
    # Normalize to a fixed-precision string: without this, an int like 100
    # passed in at creation time hashes differently from the 100.0 float
    # SQLite/SQLAlchemy returns on reload — a false tamper alarm, not a
    # real one. Always hash the same representation regardless of source.
    normalized_weight = f"{float(weight_kg):.3f}"
    payload = f"{farm_id}|{normalized_weight}|{crop_type}|{timestamp_iso}|{prev_hash}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_capture_hash(farm_id: str, weight_kg: float, crop_type: str,
                          timestamp_iso: str, geotag: str) -> str:
    """
    Client-side integrity hash — computed on the FARMER'S DEVICE at the
    moment of capture, before it ever reaches the server.

    This is a DIFFERENT hash from row_hash above. row_hash needs the
    authoritative prev_hash from the ledger and can only be computed
    server-side, at commit time, once the true last batch in the chain
    is known (an offline device can't safely know that — it might be
    stale, or two farmers might sync at nearly the same moment).

    capture_hash instead proves something narrower but still valuable:
    "this exact record wasn't altered while it sat in the offline sync
    queue on the farmer's phone." The server recomputes it on arrival
    and rejects the submission if it doesn't match.
    """
    normalized_weight = f"{float(weight_kg):.3f}"
    payload = f"{farm_id}|{normalized_weight}|{crop_type}|{timestamp_iso}|{geotag}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_chain(batches: List) -> Tuple[bool, Optional[str]]:
    """
    Walk a list of Batch rows (ordered oldest -> newest, e.g. all
    batches for one farm) and confirm the hash chain is intact.

    Returns (is_valid, first_broken_batch_id_or_None).
    """
    prev_hash = None
    for batch in batches:
        expected = compute_row_hash(
            batch.farm_id, batch.weight_kg, batch.crop_type,
            batch.timestamp.isoformat(), prev_hash or "",
        )
        if batch.row_hash != expected:
            return False, batch.batch_id
        prev_hash = batch.row_hash
    return True, None
