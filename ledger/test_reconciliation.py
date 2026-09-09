"""
Tests for the reconciliation engine. Run with:  pytest

These double as a scripted rehearsal of your live demo logic —
if these pass, your demo's core behavior works.

NOTE (updated): add_batch() no longer takes an nfc_tag_uid — tags now
bind to individual Units (see models.Unit), not whole Batches, as part
of the unit-subdivision + HMAC-signing upgrade. The checkpoint tests
below now create a Unit directly to match.

Also worth knowing: reconciliation.record_checkpoint_scan() (tested
here) is the simpler, ledger-level version. The LIVE checkpoint-scan
endpoint (api/routes/checkpoint.py) actually calls
api/services/ledger_bridge.verify_and_record_scan() instead, which
adds HMAC signature verification on top of this. Consider adding a
separate test file for that function too, since it's the one real
traffic actually goes through.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base, GIRegion, Farm, Batch, Unit
from reconciliation import add_batch, submit_downstream_claim, record_checkpoint_scan
from hash_chain import verify_chain


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def region_and_farm(db):
    region = GIRegion(name="Test Region", season_year=2026, season_certified_cap_kg=1000)
    db.add(region)
    db.commit()
    db.refresh(region)

    farm = Farm(region_id=region.region_id, name="Test Farm")
    db.add(farm)
    db.commit()
    db.refresh(farm)

    return region, farm


def test_hash_chain_integrity(db, region_and_farm):
    region, farm = region_and_farm
    add_batch(db, farm.farm_id, 100, "tea")
    add_batch(db, farm.farm_id, 150, "tea")

    batches = db.query(Batch).order_by(Batch.timestamp.asc()).all()
    is_valid, broken_id = verify_chain(batches)
    assert is_valid
    assert broken_id is None


def test_claim_approved_within_quota(db, region_and_farm):
    region, farm = region_and_farm
    batch = add_batch(db, farm.farm_id, 400, "tea")

    claim = submit_downstream_claim(db, region.region_id, "seller_1", [batch.batch_id], 300)
    assert claim.status == "approved"


def test_claim_rejected_when_exceeding_quota(db, region_and_farm):
    region, farm = region_and_farm
    batch = add_batch(db, farm.farm_id, 400, "tea")

    submit_downstream_claim(db, region.region_id, "seller_1", [batch.batch_id], 900)
    claim = submit_downstream_claim(db, region.region_id, "seller_2", [batch.batch_id], 500)

    assert claim.status == "rejected"
    assert "exceeds remaining" in claim.reason


def _make_unit(db, farm, weight_kg=100, crop_type="tea", nfc_tag_uid=None):
    """Helper: create a batch + a single Unit under it, optionally tagged."""
    batch = add_batch(db, farm.farm_id, weight_kg, crop_type)
    unit = Unit(batch_id=batch.batch_id, unit_weight_kg=weight_kg, nfc_tag_uid=nfc_tag_uid)
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit


def test_checkpoint_flags_unbound_tag(db, region_and_farm):
    scan = record_checkpoint_scan(db, "TAG-NEVER-ISSUED", "Checkpoint A")
    assert scan.flag == "unbound_tag"


def test_checkpoint_flags_duplicate_scan(db, region_and_farm):
    region, farm = region_and_farm
    _make_unit(db, farm, nfc_tag_uid="TAG-5")

    first = record_checkpoint_scan(db, "TAG-5", "Checkpoint A")
    assert first.flag is None

    second = record_checkpoint_scan(db, "TAG-5", "Checkpoint A")
    assert second.flag == "duplicate_scan"
