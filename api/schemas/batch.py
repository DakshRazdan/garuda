from typing import List
from pydantic import BaseModel


class FarmerBatchSubmission(BaseModel):
    farm_id: str
    weight_kg: float
    crop_type: str
    timestamp_iso: str
    geotag: str
    capture_hash: str


class FarmerBatchResponse(BaseModel):
    batch_id: str
    row_hash: str
    status: str


class UnitCreateRequest(BaseModel):
    batch_id: str
    unit_weight_kg: float
    quantity: int = 1


class UnitCreateResponse(BaseModel):
    batch_id: str
    created_unit_ids: List[str]


class TagBindRequest(BaseModel):
    unit_id: str
    nfc_tag_uid: str


class TagBindResponse(BaseModel):
    unit_id: str
    nfc_tag_uid: str
    hmac_signature: str

