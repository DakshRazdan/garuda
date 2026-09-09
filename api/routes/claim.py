from fastapi import APIRouter, Depends, HTTPException

from schemas.claim import ClaimSubmitRequest, ClaimSubmitResponse
from services.ledger_bridge import SessionLocal, submit_downstream_claim

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/claims", response_model=ClaimSubmitResponse)
def submit_claim(req: ClaimSubmitRequest, db=Depends(get_db)):
    try:
        claim = submit_downstream_claim(
            db, region_id=req.region_id, seller_id=req.seller_id,
            batch_ids=req.batch_ids, claimed_weight_kg=req.claimed_weight_kg,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return ClaimSubmitResponse(claim_id=claim.claim_id, status=claim.status, reason=claim.reason)
