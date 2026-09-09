from typing import Optional
from pydantic import BaseModel


class CheckpointScanRequest(BaseModel):
    tag_uid: str
    unit_id: str
    signature: str
    checkpoint_location: str
    scanner_id: Optional[str] = None


class CheckpointScanResponse(BaseModel):
    scan_id: str
    flag: Optional[str] = None
    genuine: bool
