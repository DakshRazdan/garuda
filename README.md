# GARUDA — GI Volume Reconciliation Engine

## Project Description

GARUDA is a traceability and reconciliation system for Geographical Indication (GI) tagged agricultural products such as Darjeeling Tea, Basmati Rice, and Alphonso Mango.

It targets a specific failure in existing systems: while unit-level authentication (QR codes, holograms) can verify individual products, they do not prevent total claimed volume from exceeding certified regional production. GARUDA enforces consistency at the aggregate level by tracking production, movement, and downstream claims against defined regional limits.

The system combines a tamper-evident batch ledger, NFC-based unit tagging, and quota-aware validation logic to ensure that all claims remain within verifiable production capacity.

---

## Features / Completed Functionality

- Batch registration with farm-level metadata  
- Append-only ledger with SHA-256 hash chaining  
- NFC tag binding with HMAC-based anti-cloning verification  
- End-to-end pipeline:
  - Batch creation  
  - Unit creation and tagging  
  - Checkpoint scans  
  - Claim submission and validation  
- Region-level quota enforcement  
- Rejection of over-quota claims  
- Consumer-facing tag verification  
- Regulator dashboard with quota tracking and flagged claims  
- Offline-first farmer data capture (PWA)  
- Single backend serving multiple frontends  

---

## Technology Stack

| Layer | Technology |
|------|-----------|
| Backend API | FastAPI, Uvicorn |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Ledger Integrity | SHA-256 hash chain |
| NFC Security | HMAC-SHA256 |
| Frontend | HTML, CSS, JavaScript (PWA) |
| Visualization | Chart.js |

---

## Implementation Details

- **Ledger Model**  
  Each batch entry is linked using a hash chain (`prev_hash → current_hash`) to make historical tampering detectable.

- **Reconciliation Logic**  
  Claims are validated against cumulative certified production limits per GI region. Any claim exceeding available quota is rejected.

- **NFC Tagging**  
  Each unit is associated with an NFC tag UID and signed using HMAC. Verification requires both the UID and a valid signature.

- **API Layer**  
  FastAPI routes are organized by resource (batch, claim, checkpoint, quota, verify). A service layer connects API endpoints to ledger operations.

- **Frontend Integration**  
  All frontends (farmer app, NFC tool, consumer dashboard, regulator dashboard) are served from a single API instance.

---

## Setup & Installation

### Install dependencies

```bash
cd ledger
pip install -r requirements.txt

cd ../api
pip install -r requirements.txt
```

### Configure environment

```bash
export GARUDA_HMAC_SECRET="your-secure-secret"
export DATABASE_URL="postgresql://gi_user:gi_pass@localhost:5432/gi_ledger"
```

### Seed database

```bash
cd ledger
python seed_data.py
```

### Run application

```bash
./start_demo.sh
```

Or manually:

```bash
cd api
uvicorn main:app --reload
```

### Access endpoints

- `/docs` — API documentation  
- `/regulator/` — Regulator dashboard  
- `/consumer/` — Consumer verification  
- `/nfc-capture/` — NFC tool  
- `/farmer-app/` — Farmer interface  

---

## Limitations

- No authentication or authorization on API endpoints  
- Open CORS policy  
- Static production caps (seeded values)  
- No secure key management or rotation for HMAC secrets  

---

## Future Work

- Integration with official GI certification bodies for dynamic production caps  
- Authentication and role-based access control  
- Secure key storage and rotation mechanisms  
- Audit logging and anomaly detection  
- Scalable deployment with containerization and distributed infrastructure  
- Extension to multi-region and cross-border tracking  

---

## Conclusion

GARUDA addresses a gap in GI traceability by enforcing consistency between certified production and downstream claims. It complements existing unit-level verification methods by introducing volume-level validation, ensuring that total claimed output remains within verifiable limits.
