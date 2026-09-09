from typing import List, Optional
from pydantic import BaseModel


class VerifyRequest(BaseModel):
    tag_uid: str
    unit_id: str
    signature: str
    scanner_id: Optional[str] = None


class ScanTraceEntry(BaseModel):
    checkpoint_location: str
    timestamp: str
    flag: Optional[str] = None


class VerifyResponse(BaseModel):
    genuine: bool
    flag: Optional[str] = None
    unit_id: Optional[str] = None
    batch_id: Optional[str] = None
    unit_weight_kg: Optional[float] = None
    crop_type: Optional[str] = None
    batch_weight_kg: Optional[float] = None
    farm_name: Optional[str] = None
    region_name: Optional[str] = None
    row_hash: Optional[str] = None
    timestamp: Optional[str] = None
    scanned_tag_uid: Optional[str] = None
    expected_tag_uid: Optional[str] = None
    scan_trace: List[ScanTraceEntry] = []


class QuotaResponse(BaseModel):
    region_id: str
    region_name: str
    cap_kg: float
    produced_kg: float
    claimed_kg: float
    remaining_kg: float
    pct_used: float


class MonthlyTrendPoint(BaseModel):
    month: str
    claimed_kg: float
    verified_kg: float


class MonthlyTrendResponse(BaseModel):
    region_id: str
    points: List[MonthlyTrendPoint]
