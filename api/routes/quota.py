from fastapi import APIRouter, Depends, HTTPException

from schemas.verify import QuotaResponse, MonthlyTrendResponse, MonthlyTrendPoint
from schemas.region import RegionBatchesResponse, RegionBatchItem, RegionFlaggedResponse, RegionFlaggedItem
from services.ledger_bridge import (
    SessionLocal, GIRegion, get_region_quota_status, get_monthly_claim_trend,
    list_region_batches, get_region_flagged_items,
)

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/regions")
def list_regions(db=Depends(get_db)):
    regions = db.query(GIRegion).all()
    return [{"region_id": r.region_id, "name": r.name, "season_year": r.season_year} for r in regions]


@router.get("/regions/{region_id}/quota", response_model=QuotaResponse)
def region_quota(region_id: str, db=Depends(get_db)):
    try:
        status = get_region_quota_status(db, region_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return QuotaResponse(**status)


@router.get("/regions/{region_id}/monthly-trend", response_model=MonthlyTrendResponse)
def region_monthly_trend(region_id: str, db=Depends(get_db)):
    points = get_monthly_claim_trend(db, region_id)
    return MonthlyTrendResponse(region_id=region_id, points=[MonthlyTrendPoint(**p) for p in points])


@router.get("/regions/{region_id}/batches", response_model=RegionBatchesResponse)
def region_batches(region_id: str, db=Depends(get_db)):
    batches = list_region_batches(db, region_id)
    return RegionBatchesResponse(region_id=region_id, batches=[RegionBatchItem(**b) for b in batches])


@router.get("/regions/{region_id}/flagged", response_model=RegionFlaggedResponse)
def region_flagged(region_id: str, db=Depends(get_db)):
    items = get_region_flagged_items(db, region_id)
    return RegionFlaggedResponse(region_id=region_id, items=[RegionFlaggedItem(**i) for i in items])
