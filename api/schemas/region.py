from typing import List, Optional
from pydantic import BaseModel


class RegionBatchItem(BaseModel):
    batch_id: str
    timestamp: str
    weight_kg: float
    crop_type: str
    unit_count: int
    tagged_count: int


class RegionBatchesResponse(BaseModel):
    region_id: str
    batches: List[RegionBatchItem]


class RegionFlaggedItem(BaseModel):
    ref_id: str
    kind: str
    timestamp: str
    volume_kg: float
    reason: Optional[str] = None
    status: str


class RegionFlaggedResponse(BaseModel):
    region_id: str
    items: List[RegionFlaggedItem]
