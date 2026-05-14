import json
import re
from pathlib import Path
from sqlalchemy.orm import Session
from backend.app.cms.auth import router as auth_router
from backend.app.cms.dashboard import router as dashboard_router

from fastapi import Depends, FastAPI
from backend.app.database import Base, engine, get_db
from backend.app.models import MemorialCreate, Memorial
from backend.app.cms.memorials import router as memorials_router
from backend.app.cms.audit_routes import router as audit_router

Base.metadata.create_all(bind=engine)

app = FastAPI()
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(memorials_router)
app.include_router(audit_router)

METADATA_DIR = Path("/var/www/purpaws.ca/metadata")
MEMORIAL_DIR = Path("/var/www/purpaws.ca/memorial")


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value or "memorial"


def build_memorial_html(memorial: MemorialCreate, slug: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{memorial.companion_name} Memorial | PurPaws.ca</title>
</head>
<body style="margin:0;background:#120812;color:#f8eef8;font-family:Arial;padding:40px;">
  <main style="max-width:860px;margin:0 auto;">
    <a href="/" style="color:#d4af37;text-decoration:none;letter-spacing:0.12em;text-transform:uppercase;font-size:12px;">
      PurPaws.ca — Companion Memorial Archives
    </a>

    <section style="margin-top:40px;padding:28px;border:1px solid rgba(255,255,255,0.12);border-radius:24px;background:rgba(255,255,255,0.05);">
      <div style="height:280px;border-radius:20px;background:linear-gradient(135deg,#9c6cff,#ff9fdc);display:flex;align-items:center;justify-content:center;text-transform:uppercase;letter-spacing:0.16em;font-size:12px;">
        Memorial Image Placeholder
      </div>

      <h1 style="font-size:72px;line-height:0.95;letter-spacing:-0.06em;margin:28px 0 8px;">
        {memorial.companion_name}
      </h1>

      <div style="color:#d4af37;letter-spacing:0.14em;text-transform:uppercase;font-size:12px;margin-bottom:24px;">
        {memorial.years}
      </div>

      <p style="color:#c9aeca;font-size:20px;line-height:1.55;">
        {memorial.story}
      </p>

      <hr style="border:none;border-top:1px solid rgba(255,255,255,0.12);margin:30px 0;">

      <h2>Memorial Metadata</h2>

      <p style="color:#c9aeca;">
        This memorial archive has a generated metadata endpoint:
      </p>

      <p style="word-break:break-all;font-family:monospace;color:#d4af37;">
        https://purpaws.ca/metadata/{slug}.json
      </p>
    </section>
  </main>
</body>
</html>"""


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
def create_memorial(memorial: MemorialCreate, db: Session = Depends(get_db)):
    slug = slugify(memorial.companion_name)

    db_memorial = Memorial(
        companion_name=memorial.companion_name,
        years=memorial.years,
        story=memorial.story,
        archive_type=memorial.archive_type,
        project=memorial.project,
        status="published"
    )

    db.add(db_memorial)
    db.commit()
    db.refresh(db_memorial)

    metadata = {
        "name": f"{memorial.companion_name} Memorial Archive",
        "description": memorial.story,
        "type": "Companion Memorial NFT",
        "project": memorial.project,
        "powered_by": "Eternal Ledger",
        "network": "XRPL Testnet",
        "memorial_url": f"https://purpaws.ca/memorial/{slug}",
        "attributes": [
            {
                "trait_type": "Companion Name",
                "value": memorial.companion_name
            },
            {
                "trait_type": "Years",
                "value": memorial.years
            },
            {
                "trait_type": "Archive Type",
                "value": memorial.archive_type
            },
            {
                "trait_type": "Ledger Purpose",
                "value": "Digital Continuity"
            }
        ]
    }

    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    metadata_path = METADATA_DIR / f"{slug}.json"

    with metadata_path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    memorial_path = MEMORIAL_DIR / slug
    memorial_path.mkdir(parents=True, exist_ok=True)

    html_path = memorial_path / "index.html"

    with html_path.open("w", encoding="utf-8") as f:
        f.write(build_memorial_html(memorial, slug))

    return {
        "status": "memorial and metadata created",
        "database_id": db_memorial.id,
        "slug": slug,
        "metadata_url": f"https://purpaws.ca/metadata/{slug}.json",
        "memorial_url": f"https://purpaws.ca/memorial/{slug}",
        "data": metadata
    }
