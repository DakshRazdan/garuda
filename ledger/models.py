"""
SQLAlchemy models for the GI Volume Reconciliation Engine ledger.
Owned by: Ledger & Reconciliation Lead.

These models are the source of truth for the schema. The API layer
(FastAPI, owned by a teammate) should import from here rather than
redefining anything — that keeps the two of you from drifting apart.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Float, DateTime, ForeignKey, JSON, Integer
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def gen_id() -> str:
    return str(uuid.uuid4())


class GIRegion(Base):
    __tablename__ = "gi_regions"

    region_id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)                 # e.g. "Darjeeling Tea"
    season_year = Column(Integer, nullable=False)
    season_certified_cap_kg = Column(Float, nullable=False)

    farms = relationship("Farm", back_populates="region")
    claims = relationship("DownstreamClaim", back_populates="region")


class Farm(Base):
    __tablename__ = "farms"

    farm_id = Column(String, primary_key=True, default=gen_id)
    region_id = Column(String, ForeignKey("gi_regions.region_id"), nullable=False)
    name = Column(String, nullable=False)
    geolocation = Column(String, nullable=True)            # "lat,lon" string — keep simple for MVP
    registered_capacity_estimate_kg = Column(Float, nullable=True)

    region = relationship("GIRegion", back_populates="farms")
    batches = relationship("Batch", back_populates="farm")


class Batch(Base):
    __tablename__ = "batches"

    batch_id = Column(String, primary_key=True, default=gen_id)
    farm_id = Column(String, ForeignKey("farms.farm_id"), nullable=False)
    weight_kg = Column(Float, nullable=False)
    crop_type = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Hash-chain fields — tamper-evidence, NOT a blockchain.
    prev_hash = Column(String, nullable=True)
    row_hash = Column(String, nullable=False)

    farm = relationship("Farm", back_populates="batches")
    units = relationship("Unit", back_populates="batch")


class Unit(Base):
    __tablename__ = "units"

    unit_id = Column(String, primary_key=True, default=gen_id)
    batch_id = Column(String, ForeignKey("batches.batch_id"), nullable=False)
    unit_weight_kg = Column(Float, nullable=False)
    nfc_tag_uid = Column(String, unique=True, nullable=True)
    hmac_signature = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    batch = relationship("Batch", back_populates="units")


class DownstreamClaim(Base):
    __tablename__ = "downstream_claims"

    claim_id = Column(String, primary_key=True, default=gen_id)
    region_id = Column(String, ForeignKey("gi_regions.region_id"), nullable=False)
    seller_id = Column(String, nullable=False)
    batch_ids = Column(JSON, nullable=False)               # list[str]
    claimed_weight_kg = Column(Float, nullable=False)
    status = Column(String, default="pending")              # pending | approved | rejected
    reason = Column(String, nullable=True)                  # populated on rejection
    timestamp = Column(DateTime, default=datetime.utcnow)

    region = relationship("GIRegion", back_populates="claims")


class CheckpointScan(Base):
    __tablename__ = "checkpoint_scans"

    scan_id = Column(String, primary_key=True, default=gen_id)
    tag_uid = Column(String, nullable=False)
    checkpoint_location = Column(String, nullable=False)
    scanner_id = Column(String, nullable=True)
    flag = Column(String, nullable=True)                    # "unbound_tag" | "duplicate_scan" | None
    timestamp = Column(DateTime, default=datetime.utcnow)
