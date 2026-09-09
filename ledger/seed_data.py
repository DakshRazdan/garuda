import random
from datetime import datetime

from database import init_db, SessionLocal
from models import GIRegion, Farm, Unit
from reconciliation import add_batch, submit_downstream_claim, record_checkpoint_scan
import security

random.seed(42)

REGIONS = [
    {
        "name": "Darjeeling Tea",
        "cap_kg": 9000,
        "crop_type": "tea",
        "claim_ratio": 0.82,
        "farms": ["Makaibari Estate", "Castleton Estate", "Glenburn Estate",
                  "Happy Valley Estate", "Margaret's Hope Estate"],
    },
    {
        "name": "Basmati Rice (Punjab)",
        "cap_kg": 15000,
        "crop_type": "rice",
        "claim_ratio": 0.35,
        "farms": ["Amritsar FPO Cluster", "Ludhiana Grower Collective",
                  "Patiala Basmati Co-op", "Gurdaspur Farmer Group"],
    },
    {
        "name": "Alphonso Mango (Ratnagiri)",
        "cap_kg": 6000,
        "crop_type": "mango",
        "claim_ratio": 0.93,
        "farms": ["Konkan Fruit Growers", "Ratnagiri Orchard Collective",
                  "Devgad Alphonso Co-op"],
    },
]


def run():
    init_db()
    db = SessionLocal()
    tag_counter = 0
    first_tagged_uid = None

    for region_def in REGIONS:
        region = GIRegion(
            name=region_def["name"], season_year=2026,
            season_certified_cap_kg=region_def["cap_kg"],
        )
        db.add(region)
        db.commit()
        db.refresh(region)

        farms = []
        for farm_name in region_def["farms"]:
            farm = Farm(
                region_id=region.region_id, name=farm_name,
                registered_capacity_estimate_kg=region_def["cap_kg"] / len(region_def["farms"]),
            )
            db.add(farm)
            farms.append(farm)
        db.commit()
        for f in farms:
            db.refresh(f)

        target_total = region_def["cap_kg"] * 0.7
        logged = 0.0
        batches = []
        while logged < target_total:
            farm = random.choice(farms)
            weight = round(random.uniform(150, 650), 1)
            if logged + weight > target_total:
                weight = round(target_total - logged, 1)
                if weight <= 0:
                    break
            batch = add_batch(db, farm.farm_id, weight_kg=weight, crop_type=region_def["crop_type"])
            batches.append(batch)
            logged += weight

        print(f"{region.name}: {len(farms)} farms, {len(batches)} batches, {logged:.1f} kg logged / {region.season_certified_cap_kg} kg cap")

        units_tagged = 0
        for batch in batches:
            unit_weight = round(random.uniform(0.2, 2.0), 2)
            max_units = max(1, int(batch.weight_kg // unit_weight))
            unit_count = min(max_units, random.randint(3, 10))
            for i in range(unit_count):
                unit = Unit(batch_id=batch.batch_id, unit_weight_kg=unit_weight)
                db.add(unit)
                db.commit()
                db.refresh(unit)

                if random.random() < 0.6:
                    tag_uid = f"NFC-{region.region_id[:6]}-{tag_counter:04d}"
                    tag_counter += 1
                    unit.nfc_tag_uid = tag_uid
                    # Uses the SAME signing function the live API uses (security.sign),
                    # not a lookalike copy — otherwise seeded units would fail real
                    # signature verification the moment anyone scanned/checked them.
                    unit.hmac_signature = security.sign(unit.unit_id, batch.row_hash, tag_uid)
                    db.add(unit)
                    db.commit()
                    units_tagged += 1
                    if first_tagged_uid is None:
                        first_tagged_uid = tag_uid

        print(f"  units created and tagged: {units_tagged}")

        approved = submit_downstream_claim(
            db, region.region_id, seller_id=f"{region.name.split()[0]}Exports Pvt Ltd",
            batch_ids=[], claimed_weight_kg=round(region_def["cap_kg"] * region_def["claim_ratio"], 1),
        )
        print(f"  demo claim (should be approved): {approved.status}")

    record_checkpoint_scan(db, first_tagged_uid, "Siliguri Checkpoint")
    record_checkpoint_scan(db, first_tagged_uid, "Siliguri Checkpoint")
    record_checkpoint_scan(db, "NFC-FAKE-CLONE-9999", "Kolkata Port Checkpoint")

    print("\nDone. Pre-populated: 3 GI regions, randomized batches split into tagged and untagged units, "
          "3 approved claims, and 3 checkpoint scans (one duplicate, one unbound) ready to show on the dashboard.")
    db.close()


if __name__ == "__main__":
    run()
