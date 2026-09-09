from fastapi import APIRouter, Depends

from schemas.checkpoint import CheckpointScanRequest, CheckpointScanResponse
from services.ledger_bridge import SessionLocal, verify_and_record_scan

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/checkpoints/scan", response_model=CheckpointScanResponse)
def checkpoint_scan(req: CheckpointScanRequest, db=Depends(get_db)):
    unit, batch, flag, scan = verify_and_record_scan(
        db, tag_uid=req.tag_uid, unit_id=req.unit_id, signature=req.signature,
        checkpoint_location=req.checkpoint_location, scanner_id=req.scanner_id,
        source="checkpoint",
    )
    return CheckpointScanResponse(scan_id=scan.scan_id, flag=flag, genuine=flag is None)
