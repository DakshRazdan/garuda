from fastapi import APIRouter, Depends

from schemas.verify import VerifyRequest, VerifyResponse
from services.ledger_bridge import SessionLocal, log_consumer_scan, get_unit_full_record

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/verify", response_model=VerifyResponse)
def verify_tag(req: VerifyRequest, db=Depends(get_db)):
    unit, batch, flag, scan = log_consumer_scan(
        db, tag_uid=req.tag_uid, unit_id=req.unit_id,
        signature=req.signature, scanner_id=req.scanner_id,
    )

    if flag is not None or unit is None:
        expected_uid = unit.nfc_tag_uid if (unit is not None and flag == "uid_mismatch") else None
        return VerifyResponse(
            genuine=False, flag=flag, unit_id=req.unit_id,
            scanned_tag_uid=req.tag_uid, expected_tag_uid=expected_uid,
        )

    record = get_unit_full_record(db, unit.unit_id)
    if record is None:
        return VerifyResponse(genuine=False, flag="unregistered_unit", unit_id=req.unit_id)

    full_unit, full_batch, farm, region, scans = record
    trace = [
        {"checkpoint_location": s.checkpoint_location, "timestamp": s.timestamp.isoformat(), "flag": s.flag}
        for s in scans
    ]
    return VerifyResponse(
        genuine=True,
        flag=None,
        unit_id=full_unit.unit_id,
        batch_id=full_batch.batch_id if full_batch else None,
        unit_weight_kg=full_unit.unit_weight_kg,
        crop_type=full_batch.crop_type if full_batch else None,
        batch_weight_kg=full_batch.weight_kg if full_batch else None,
        farm_name=farm.name if farm else None,
        region_name=region.name if region else None,
        row_hash=full_batch.row_hash if full_batch else None,
        timestamp=full_unit.created_at.isoformat(),
        scanned_tag_uid=req.tag_uid,
        scan_trace=trace,
    )
