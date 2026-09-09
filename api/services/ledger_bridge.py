import os
import sys
from collections import defaultdict
from typing import Optional

LEDGER_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "ledger"))
if LEDGER_PATH not in sys.path:
    sys.path.append(LEDGER_PATH)

if "DATABASE_URL" not in os.environ:
    db_file = os.path.join(LEDGER_PATH, "gi_ledger.db")
    os.environ["DATABASE_URL"] = f"sqlite:///{db_file}"

from database import SessionLocal, init_db
from models import Farm, Batch, Unit, GIRegion, DownstreamClaim, CheckpointScan
from reconciliation import add_batch, submit_downstream_claim, get_region_quota_status
from hash_chain import compute_capture_hash

from . import security


def list_batches_with_capacity(db):
    batches = db.query(Batch).order_by(Batch.timestamp.desc()).all()
    results = []
    for b in batches:
        allocated = sum(u.unit_weight_kg for u in db.query(Unit).filter(Unit.batch_id == b.batch_id).all())
        remaining = round(b.weight_kg - allocated, 3)
        if remaining <= 0:
            continue
        farm = db.query(Farm).filter(Farm.farm_id == b.farm_id).first()
        results.append({
            "batch_id": b.batch_id,
            "farm_name": farm.name if farm else None,
            "crop_type": b.crop_type,
            "weight_kg": b.weight_kg,
            "remaining_kg": remaining,
            "timestamp": b.timestamp.isoformat(),
        })
    return results


def create_units(db, batch_id: str, unit_weight_kg: float, quantity: int = 1):
    batch = db.query(Batch).filter(Batch.batch_id == batch_id).first()
    if batch is None:
        raise ValueError(f"Unknown batch_id: {batch_id}")
    if quantity < 1:
        raise ValueError("quantity must be at least 1")

    allocated = sum(u.unit_weight_kg for u in db.query(Unit).filter(Unit.batch_id == batch_id).all())
    requested = unit_weight_kg * quantity
    remaining = batch.weight_kg - allocated
    if requested > remaining + 1e-6:
        raise ValueError(
            f"Requested {requested}kg across {quantity} units exceeds remaining batch capacity of {round(remaining,3)}kg"
        )

    created = []
    for _ in range(quantity):
        unit = Unit(batch_id=batch_id, unit_weight_kg=unit_weight_kg)
        db.add(unit)
        db.commit()
        db.refresh(unit)
        created.append(unit)
    return created


def list_unbound_units(db):
    units = (
        db.query(Unit)
        .filter(Unit.nfc_tag_uid.is_(None))
        .order_by(Unit.created_at.desc())
        .all()
    )
    results = []
    for u in units:
        batch = db.query(Batch).filter(Batch.batch_id == u.batch_id).first()
        farm = db.query(Farm).filter(Farm.farm_id == batch.farm_id).first() if batch else None
        results.append({
            "unit_id": u.unit_id,
            "batch_id": u.batch_id,
            "farm_name": farm.name if farm else None,
            "crop_type": batch.crop_type if batch else None,
            "unit_weight_kg": u.unit_weight_kg,
            "created_at": u.created_at.isoformat(),
        })
    return results


def bind_nfc_tag(db, unit_id: str, nfc_tag_uid: str) -> Unit:
    unit = db.query(Unit).filter(Unit.unit_id == unit_id).first()
    if unit is None:
        raise ValueError(f"Unknown unit_id: {unit_id}")
    if unit.nfc_tag_uid is not None:
        raise ValueError(f"Unit {unit_id} already has a tag bound")

    existing = db.query(Unit).filter(Unit.nfc_tag_uid == nfc_tag_uid).first()
    if existing is not None:
        raise ValueError(f"Tag {nfc_tag_uid} is already bound to another unit")

    batch = db.query(Batch).filter(Batch.batch_id == unit.batch_id).first()
    if batch is None:
        raise ValueError(f"Unit {unit_id} has no parent batch")

    signature = security.sign(unit.unit_id, batch.row_hash, nfc_tag_uid)
    unit.nfc_tag_uid = nfc_tag_uid
    unit.hmac_signature = signature
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit


def verify_and_record_scan(db, tag_uid: str, unit_id: str, signature: str,
                            checkpoint_location: str, scanner_id: Optional[str] = None,
                            source: str = "checkpoint"):
    unit = db.query(Unit).filter(Unit.unit_id == unit_id).first()

    flag = None
    batch = None
    if unit is None:
        flag = "unregistered_unit"
    else:
        batch = db.query(Batch).filter(Batch.batch_id == unit.batch_id).first()
        if unit.nfc_tag_uid != tag_uid:
            flag = "uid_mismatch"
        elif batch is None or not security.verify(unit.unit_id, batch.row_hash, unit.nfc_tag_uid, signature):
            flag = "signature_mismatch"
        else:
            if source == "checkpoint":
                prior = (
                    db.query(CheckpointScan)
                    .filter(CheckpointScan.tag_uid == tag_uid,
                            CheckpointScan.checkpoint_location == checkpoint_location)
                    .first()
                )
                if prior is not None:
                    flag = "duplicate_scan"

    scan = CheckpointScan(
        tag_uid=tag_uid, checkpoint_location=checkpoint_location,
        scanner_id=scanner_id, flag=flag,
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)

    return unit, batch, flag, scan


def get_unit_full_record(db, unit_id: str):
    unit = db.query(Unit).filter(Unit.unit_id == unit_id).first()
    if unit is None:
        return None
    batch = db.query(Batch).filter(Batch.batch_id == unit.batch_id).first()
    farm = db.query(Farm).filter(Farm.farm_id == batch.farm_id).first() if batch else None
    region = None
    if farm is not None:
        region = db.query(GIRegion).filter(GIRegion.region_id == farm.region_id).first()
    scans = (
        db.query(CheckpointScan)
        .filter(CheckpointScan.tag_uid == unit.nfc_tag_uid)
        .order_by(CheckpointScan.timestamp.asc())
        .all()
    )
    return unit, batch, farm, region, scans


def list_region_batches(db, region_id: str):
    farms = db.query(Farm).filter(Farm.region_id == region_id).all()
    farm_ids = [f.farm_id for f in farms]
    batches = (
        db.query(Batch)
        .filter(Batch.farm_id.in_(farm_ids))
        .order_by(Batch.timestamp.desc())
        .all()
    )
    results = []
    for b in batches:
        units = db.query(Unit).filter(Unit.batch_id == b.batch_id).all()
        tagged_count = sum(1 for u in units if u.nfc_tag_uid is not None)
        results.append({
            "batch_id": b.batch_id, "timestamp": b.timestamp.isoformat(),
            "weight_kg": b.weight_kg, "crop_type": b.crop_type,
            "unit_count": len(units), "tagged_count": tagged_count,
        })
    return results


def get_region_flagged_items(db, region_id: str):
    items = []

    claims = (
        db.query(DownstreamClaim)
        .filter(DownstreamClaim.region_id == region_id, DownstreamClaim.status == "rejected")
        .all()
    )
    for c in claims:
        items.append({
            "ref_id": c.claim_id, "kind": "claim", "timestamp": c.timestamp.isoformat(),
            "volume_kg": c.claimed_weight_kg, "reason": c.reason, "status": "Rejected",
        })

    scans = db.query(CheckpointScan).filter(CheckpointScan.flag.isnot(None)).all()
    for s in scans:
        unit = db.query(Unit).filter(Unit.nfc_tag_uid == s.tag_uid).first()
        if unit is None:
            continue
        batch = db.query(Batch).filter(Batch.batch_id == unit.batch_id).first()
        if batch is None:
            continue
        farm = db.query(Farm).filter(Farm.farm_id == batch.farm_id).first()
        if farm is None or farm.region_id != region_id:
            continue
        items.append({
            "ref_id": unit.unit_id, "kind": "scan", "timestamp": s.timestamp.isoformat(),
            "volume_kg": unit.unit_weight_kg, "reason": s.flag, "status": "Under review",
        })

    items.sort(key=lambda x: x["timestamp"], reverse=True)
    return items


def get_monthly_claim_trend(db, region_id: str):
    claims = (
        db.query(DownstreamClaim)
        .filter(DownstreamClaim.region_id == region_id)
        .order_by(DownstreamClaim.timestamp.asc())
        .all()
    )

    buckets = defaultdict(lambda: {"claimed_kg": 0.0, "verified_kg": 0.0})
    for c in claims:
        key = c.timestamp.strftime("%Y-%m")
        buckets[key]["claimed_kg"] += c.claimed_weight_kg
        if c.status == "approved":
            buckets[key]["verified_kg"] += c.claimed_weight_kg

    months = sorted(buckets.keys())
    return [
        {"month": m, "claimed_kg": round(buckets[m]["claimed_kg"], 1),
         "verified_kg": round(buckets[m]["verified_kg"], 1)}
        for m in months
    ]


def log_consumer_scan(db, tag_uid: str, unit_id: str, signature: str, scanner_id: Optional[str] = None):
    return verify_and_record_scan(
        db, tag_uid=tag_uid, unit_id=unit_id, signature=signature,
        checkpoint_location="Consumer App", scanner_id=scanner_id, source="consumer",
    )
