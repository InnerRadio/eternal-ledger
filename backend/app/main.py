from fastapi import FastAPI
from backend.app.models import MemorialCreate

app = FastAPI()

@app.get("/")
def root():
    return {
        "project": "Eternal Ledger",
        "deployment": "PurPaws",
        "status": "active",
        "network": "XRPL Testnet"
    }

@app.get("/memorial/bailey")
def bailey_memorial():
    return {
        "name": "Bailey",
        "years": "2012 — 2026",
        "type": "Companion Memorial",
        "project": "PurPaws",
        "ledger": "XRPL Testnet"
    }

@app.post("/create-memorial")
def create_memorial(memorial: MemorialCreate):
    return {
        "status": "memorial received",
        "data": memorial.dict()
    }
