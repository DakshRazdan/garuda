import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from services.ledger_bridge import init_db
from routes import batch, checkpoint, claim, quota, verify

app = FastAPI(title="GARUDA API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


app.include_router(batch.router)
app.include_router(checkpoint.router)
app.include_router(claim.router)
app.include_router(quota.router)
app.include_router(verify.router)


@app.get("/health")
def health():
    return {"status": "ok"}


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
app.mount("/farmer-app", StaticFiles(directory=os.path.join(REPO_ROOT, "ledger", "farmer_app"), html=True), name="farmer-app")
app.mount("/nfc-capture", StaticFiles(directory=os.path.join(REPO_ROOT, "nfc-capture"), html=True), name="nfc-capture")
app.mount("/consumer", StaticFiles(directory=os.path.join(REPO_ROOT, "consumer-dashboard"), html=True), name="consumer")
app.mount("/regulator", StaticFiles(directory=os.path.join(REPO_ROOT, "regulator-dashboard"), html=True), name="regulator")
