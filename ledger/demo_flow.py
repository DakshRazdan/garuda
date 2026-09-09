import sys
import requests

from hash_chain import compute_capture_hash

API_BASE = "http://localhost:8001"


def fail(message):
    print(f"FAILED: {message}")
    sys.exit(1)


def step(n, title):
    print(f"\n{n}. {title}")


def main():
    try:
        requests.get(f"{API_BASE}/health", timeout=3)
    except requests.exceptions.ConnectionError:
        fail(f"Could not reach {API_BASE}. Start the API first: uvicorn main:app --reload")

    regions = requests.get(f"{API_BASE}/regions").json()
    if not regions:
        fail("No regions found. Run ledger/seed_data.py first.")
    region = regions[0]
    region_id = region["region_id"]
    print(f"Using region: {region['name']}")

    farms = requests.get(f"{API_BASE}/farmer/farms").json()
    farm = next((f for f in farms if f["region_id"] == region_id), None)
    if farm is None:
        fail("No farm found for the selected region.")
    farm_id = farm["farm_id"]
    print(f"Using farm: {farm['name']}")

    step(1, "Creating batch...")
    weight_kg = 10.0
    crop_type = "demo_crop"
    timestamp_iso = "2026-09-03T00:00:00"
    geotag = "26.5,88.3"
    capture_hash = compute_capture_hash(farm_id, weight_kg, crop_type, timestamp_iso, geotag)

    res = requests.post(f"{API_BASE}/farmer/batches", json={
        "farm_id": farm_id, "weight_kg": weight_kg, "crop_type": crop_type,
        "timestamp_iso": timestamp_iso, "geotag": geotag, "capture_hash": capture_hash,
    })
    if res.status_code != 200:
        fail(f"batch creation failed: {res.text}")
    batch = res.json()
    print(f"   Batch ID: {batch['batch_id']}")
    print(f"   Row hash: {batch['row_hash']}")
    print(f"   Status: {batch['status']}")

    step(2, "Creating a unit from the batch...")
    res = requests.post(f"{API_BASE}/units", json={
        "batch_id": batch["batch_id"], "unit_weight_kg": 1.0, "quantity": 1,
    })
    if res.status_code != 200:
        fail(f"unit creation failed: {res.text}")
    unit_id = res.json()["created_unit_ids"][0]
    print(f"   Unit ID: {unit_id}")

    step(3, "Binding NFC tag to unit...")
    tag_uid = "DEMO-TAG-0001"
    res = requests.post(f"{API_BASE}/units/bind-tag", json={
        "unit_id": unit_id, "nfc_tag_uid": tag_uid,
    })
    if res.status_code != 200:
        fail(f"tag binding failed: {res.text}")
    bound = res.json()
    signature = bound["hmac_signature"]
    print(f"   Tag UID: {tag_uid}")
    print(f"   HMAC signature: {signature}")

    step(4, "Simulating checkpoint scan (genuine tag)...")
    res = requests.post(f"{API_BASE}/checkpoints/scan", json={
        "tag_uid": tag_uid, "unit_id": unit_id, "signature": signature,
        "checkpoint_location": "Demo Checkpoint",
    })
    if res.status_code != 200:
        fail(f"checkpoint scan failed: {res.text}")
    scan = res.json()
    print(f"   Result: {'genuine' if scan['genuine'] else 'flagged'}")
    print(f"   Flag: {scan['flag']}")

    quota = requests.get(f"{API_BASE}/regions/{region_id}/quota").json()
    remaining = quota["remaining_kg"]
    print(f"\nRegion remaining headroom before claims: {remaining} kg")

    step(5, "Submitting downstream claim within quota...")
    within_quota = round(remaining * 0.1, 1)
    res = requests.post(f"{API_BASE}/claims", json={
        "region_id": region_id, "seller_id": "Demo Exports Pvt Ltd",
        "batch_ids": [batch["batch_id"]], "claimed_weight_kg": within_quota,
    })
    if res.status_code != 200:
        fail(f"claim submission failed: {res.text}")
    approved_claim = res.json()
    print(f"   Claim ID: {approved_claim['claim_id']}")
    print(f"   Status: {approved_claim['status']}")
    print(f"   Reason: {approved_claim['reason']}")

    step(6, "Submitting downstream claim EXCEEDING quota...")
    over_quota = round(remaining * 1.5, 1)
    res = requests.post(f"{API_BASE}/claims", json={
        "region_id": region_id, "seller_id": "Demo Exports Pvt Ltd",
        "batch_ids": [batch["batch_id"]], "claimed_weight_kg": over_quota,
    })
    if res.status_code != 200:
        fail(f"claim submission failed: {res.text}")
    rejected_claim = res.json()
    print(f"   Claim ID: {rejected_claim['claim_id']}")
    print(f"   Status: {rejected_claim['status']}")
    print(f"   Reason: {rejected_claim['reason']}")

    step(7, "Consumer verifying genuine tag...")
    res = requests.post(f"{API_BASE}/verify", json={
        "tag_uid": tag_uid, "unit_id": unit_id, "signature": signature,
    })
    verify_genuine = res.json()
    print(f"   Genuine: {verify_genuine['genuine']}")
    print(f"   Product: {verify_genuine['crop_type']}")
    print(f"   Farm: {verify_genuine['farm_name']}")
    print(f"   Region: {verify_genuine['region_name']}")

    step(8, "Consumer verifying a CLONED tag (same unit_id and signature, different physical UID)...")
    res = requests.post(f"{API_BASE}/verify", json={
        "tag_uid": "FAKE-CLONE-UID-9999", "unit_id": unit_id, "signature": signature,
    })
    verify_clone = res.json()
    print(f"   Genuine: {verify_clone['genuine']}")
    print(f"   Flag: {verify_clone['flag']}")
    print(f"   Expected UID: {verify_clone['expected_tag_uid']}")
    print(f"   Scanned UID: {verify_clone['scanned_tag_uid']}")

    print("\nAll steps completed. Pipeline verified end to end.")

    if approved_claim["status"] != "approved":
        fail("expected step 5 claim to be approved")
    if rejected_claim["status"] != "rejected":
        fail("expected step 6 claim to be rejected")
    if not verify_genuine["genuine"]:
        fail("expected step 7 verification to be genuine")
    if verify_clone["genuine"] or verify_clone["flag"] != "uid_mismatch":
        fail("expected step 8 verification to be flagged as uid_mismatch")

    print("All checks passed.")


if __name__ == "__main__":
    main()
