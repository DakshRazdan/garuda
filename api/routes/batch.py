from fastapi import APIRouter, Depends, HTTPException

from schemas.batch import (
    FarmerBatchSubmission, FarmerBatchResponse,
    UnitCreateRequest, UnitCreateResponse,
    TagBindRequest, TagBindResponse,
)
from services.ledger_bridge import (
    SessionLocal, Farm, add_batch, compute_capture_hash,
    bind_nfc_tag, list_unbound_units, list_batches_with_capacity, create_units,
)

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/farmer/batches", response_model=FarmerBatchResponse)
def submit_farmer_batch(submission: FarmerBatchSubmission, db=Depends(get_db)):
    expected_hash = compute_capture_hash(
        submission.farm_id, submission.weight_kg, submission.crop_type,
        submission.timestamp_iso, submission.geotag,
    )
    if submission.capture_hash != expected_hash:
        raise HTTPException(status_code=400, detail="Integrity check failed, submission does not match capture_hash")

    farm = db.query(Farm).filter(Farm.farm_id == submission.farm_id).first()
    if farm is None:
        raise HTTPException(status_code=404, detail=f"Unknown farm_id: {submission.farm_id}")

    batch = add_batch(
        db, farm_id=submission.farm_id, weight_kg=submission.weight_kg,
        crop_type=submission.crop_type,
    )
    return FarmerBatchResponse(batch_id=batch.batch_id, row_hash=batch.row_hash, status="committed")


@router.get("/farmer/farms")
def list_farms(db=Depends(get_db)):
    farms = db.query(Farm).all()
    return [{"farm_id": f.farm_id, "name": f.name, "region_id": f.region_id} for f in farms]


@router.get("/batches/with-capacity")
def batches_with_capacity(db=Depends(get_db)):
    return list_batches_with_capacity(db)


@router.post("/units", response_model=UnitCreateResponse)
def create_units_route(req: UnitCreateRequest, db=Depends(get_db)):
    try:
        units = create_units(db, req.batch_id, req.unit_weight_kg, req.quantity)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return UnitCreateResponse(batch_id=req.batch_id, created_unit_ids=[u.unit_id for u in units])


@router.get("/units/unbound")
def unbound_units(db=Depends(get_db)):
    return list_unbound_units(db)


@router.post("/units/bind-tag", response_model=TagBindResponse)
def bind_tag(req: TagBindRequest, db=Depends(get_db)):
    try:
        unit = bind_nfc_tag(db, req.unit_id, req.nfc_tag_uid)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return TagBindResponse(unit_id=unit.unit_id, nfc_tag_uid=unit.nfc_tag_uid, hmac_signature=unit.hmac_signature)
