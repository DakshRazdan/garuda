"""
Core reconciliation engine — the actual "novel" logic of this project.

Deliberately rule-based, not ML: this needs to stay explainable and
auditable, the same way real-world ISO 22095 mass-balance systems work.

Owned by: Ledger & Reconciliation Lead.
The API layer (owned by a teammate) should only ever call these
functions — it shouldn't touch models/session logic directly. Keeping
that boundary clean means their endpoints stay thin wrappers around
this file, and you can both work in parallel without merge conflicts.
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session

from models import Farm, Batch, Unit, GIRegion, DownstreamClaim, CheckpointScan
from hash_chain import compute_row_hash


def add_batch(db: Session, farm_id: str, weight_kg: float, crop_type: str) -> Batch:
    """Log a new procurement batch, hash-chained to the farm's last batch."""
    farm = db.query(Farm).filter(Farm.farm_id == farm_id).first()
    if farm is None:
        raise ValueError(f"Unknown farm_id: {farm_id}")

    last_batch = (
        db.query(Batch)
        .filter(Batch.farm_id == farm_id)
        .order_by(Batch.timestamp.desc())
        .first()
    )
    prev_hash = last_batch.row_hash if last_batch else None
    timestamp = datetime.utcnow()

    row_hash = compute_row_hash(
        farm_id, weight_kg, crop_type, timestamp.isoformat(), prev_hash or "",
    )

    batch = Batch(
        farm_id=farm_id, weight_kg=weight_kg, crop_type=crop_type,
        timestamp=timestamp, prev_hash=prev_hash, row_hash=row_hash,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def get_region_quota_status(db: Session, region_id: str) -> dict:
    """Live quota status for a region: produced, cap, remaining, % used."""
    region = db.query(GIRegion).filter(GIRegion.region_id == region_id).first()
    if region is None:
        raise ValueError(f"Unknown region_id: {region_id}")

    produced_rows = (
        db.query(Batch.weight_kg)
        .join(Farm, Batch.farm_id == Farm.farm_id)
        .filter(Farm.region_id == region_id)
        .all()
    )
    produced_kg = sum(w[0] for w in produced_rows)

    approved_rows = (
        db.query(DownstreamClaim.claimed_weight_kg)
        .filter(DownstreamClaim.region_id == region_id, DownstreamClaim.status == "approved")
        .all()
    )
    claimed_kg = sum(c[0] for c in approved_rows)

    remaining_kg = region.season_certified_cap_kg - claimed_kg

    return {
        "region_id": region_id,
        "region_name": region.name,
        "cap_kg": region.season_certified_cap_kg,
        "produced_kg": produced_kg,
        "claimed_kg": claimed_kg,
        "remaining_kg": remaining_kg,
        "pct_used": round((claimed_kg / region.season_certified_cap_kg) * 100, 1)
                    if region.season_certified_cap_kg else 0,
    }


def submit_downstream_claim(db: Session, region_id: str, seller_id: str,
                             batch_ids: List[str], claimed_weight_kg: float) -> DownstreamClaim:
    """
    The core fraud-catching step: approve a downstream claim only if it
    fits within the region's remaining certified headroom. This is the
    "you cannot sell more than was grown" check.
    """
    status_before = get_region_quota_status(db, region_id)
    remaining = status_before["remaining_kg"]

    if claimed_weight_kg <= remaining:
        status, reason = "approved", None
    else:
        status = "rejected"
        shortfall = round(claimed_weight_kg - remaining, 2)
        reason = f"Claim exceeds remaining regional headroom by {shortfall} kg"

    claim = DownstreamClaim(
        region_id=region_id, seller_id=seller_id, batch_ids=batch_ids,
        claimed_weight_kg=claimed_weight_kg, status=status, reason=reason,
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return claim


def record_checkpoint_scan(db: Session, tag_uid: str, checkpoint_location: str,
                            scanner_id: Optional[str] = None) -> CheckpointScan:
    """
    Log an NFC checkpoint scan. Flags:
      - "unbound_tag": tag_uid doesn't match any known unit (never
        legitimately written, or a cloned/blank tag).
      - "duplicate_scan": same tag already scanned at this checkpoint
        before — a signal of possible tag cloning/reuse.
    """
    bound_unit = db.query(Unit).filter(Unit.nfc_tag_uid == tag_uid).first()
    flag = None

    if bound_unit is None:
        flag = "unbound_tag"
    else:
        prior_scan = (
            db.query(CheckpointScan)
            .filter(CheckpointScan.tag_uid == tag_uid,
                    CheckpointScan.checkpoint_location == checkpoint_location)
            .first()
        )
        if prior_scan is not None:
            flag = "duplicate_scan"

    scan = CheckpointScan(
        tag_uid=tag_uid, checkpoint_location=checkpoint_location,
        scanner_id=scanner_id, flag=flag,
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)
    return scan
