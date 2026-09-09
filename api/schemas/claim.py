from typing import List, Optional
from pydantic import BaseModel


class ClaimSubmitRequest(BaseModel):
    region_id: str
    seller_id: str
    batch_ids: List[str] = []
    claimed_weight_kg: float


class ClaimSubmitResponse(BaseModel):
    claim_id: str
    status: str
    reason: Optional[str] = None
