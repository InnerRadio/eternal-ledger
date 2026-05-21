from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, UploadFile
from PIL import Image
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import MediaAsset, MediaAssetCreate
from backend.app.cms.security import require_roles

UPLOAD_DIR = Path("/var/www/eternal-ledger-github/uploads/media")
THUMBNAIL_DIR = Path("/var/www/eternal-ledger-github/uploads/thumbnails")

router = APIRouter(prefix="/cms/media", tags=["CMS Media"])


def create_image_thumbnail(source_path: Path, stored_filename: str):
    THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)

    thumb_name = f"{Path(stored_filename).stem}.jpg"
    thumb_path = THUMBNAIL_DIR / thumb_name

    with Image.open(source_path) as img:
        img.thumbnail((480, 480))
        img.convert("RGB").save(thumb_path, "JPEG", quality=85)

    return f"/uploads/thumbnails/{thumb_name}"


def serialize_media_asset(asset: MediaAsset):
    return {
        "id": asset.id,
        "memorial_id": asset.memorial_id,
        "file_path": asset.file_path,
        "original_filename": asset.original_filename,
        "media_type": asset.media_type,
        "status": asset.status,
        "uploaded_by_user_id": asset.uploaded_by_user_id,
        "ipfs_cid": asset.ipfs_cid,
        "xrpl_tx_hash": asset.xrpl_tx_hash,
        "created_at": asset.created_at,
    }


@router.get("/")
def list_media_assets(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "editor", "reviewer"))
):
    assets = db.query(MediaAsset).all()

    return {
        "module": "CMS Media",
        "status": "active",
        "count": len(assets),
        "records": [
            serialize_media_asset(asset)
            for asset in assets
        ]
    }


@router.post("/")
def create_media_asset(
    payload: MediaAssetCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "editor"))
):
    asset = MediaAsset(
        memorial_id=payload.memorial_id,
        file_path=payload.file_path,
        original_filename=payload.original_filename,
        media_type=payload.media_type,
        status=payload.status,
        uploaded_by_user_id=current_user.get("user_id"),
    )

    db.add(asset)
    db.commit()
    db.refresh(asset)

    return {
        "module": "CMS Media",
        "status": "created",
        "record": serialize_media_asset(asset)
    }


@router.post("/upload")
async def upload_media_asset(
    file: UploadFile = File(...),
    memorial_id: int | None = Form(None),
    media_type: str = Form("image"),
    status: str = Form("draft"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "editor"))
):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    if memorial_id == 0:
        memorial_id = None

    original_filename = file.filename or "uploaded-file"
    extension = Path(original_filename).suffix.lower()
    stored_filename = f"{uuid4().hex}{extension}"
    stored_path = UPLOAD_DIR / stored_filename

    content = await file.read()
    stored_path.write_bytes(content)

    public_file_path = f"/uploads/media/{stored_filename}"

    thumbnail_path = None
    if media_type == "image":
        try:
            thumbnail_path = create_image_thumbnail(stored_path, stored_filename)
        except Exception:
            thumbnail_path = None

    asset = MediaAsset(
        memorial_id=memorial_id,
        file_path=public_file_path,
        original_filename=original_filename,
        media_type=media_type,
        status=status,
        uploaded_by_user_id=current_user.get("user_id"),
    )

    db.add(asset)
    db.commit()
    db.refresh(asset)

    return {
        "module": "CMS Media",
        "status": "uploaded",
        "record": serialize_media_asset(asset)
    }


@router.get("/memorial/{memorial_id}")
def get_memorial_media(
    memorial_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "editor", "reviewer"))
):
    assets = db.query(MediaAsset).filter(
        MediaAsset.memorial_id == memorial_id
    ).all()

    return {
        "module": "CMS Media",
        "status": "active",
        "memorial_id": memorial_id,
        "count": len(assets),
        "records": [
            serialize_media_asset(asset)
            for asset in assets
        ]
    }


@router.post("/{asset_id}/pin-ipfs")
def pin_media_asset_to_ipfs(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin"))
):
    asset = db.query(MediaAsset).filter(MediaAsset.id == asset_id).first()

    if not asset:
        return {
            "module": "CMS Media",
            "status": "error",
            "message": "Media asset not found."
        }

    return {
        "module": "CMS Media",
        "status": "pending",
        "message": "IPFS pinning is not configured yet.",
        "record": serialize_media_asset(asset)
    }


@router.post("/{asset_id}/anchor-xrpl")
def anchor_media_asset_to_xrpl(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin"))
):
    asset = db.query(MediaAsset).filter(MediaAsset.id == asset_id).first()

    if not asset:
        return {
            "module": "CMS Media",
            "status": "error",
            "message": "Media asset not found."
        }

    return {
        "module": "CMS Media",
        "status": "pending",
        "message": "XRPL anchoring endpoint exists, but live transaction submission is not wired into CMS yet.",
        "record": serialize_media_asset(asset)
    }


@router.delete("/{asset_id}")
def delete_media_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin"))
):
    asset = db.query(MediaAsset).filter(MediaAsset.id == asset_id).first()

    if not asset:
        return {
            "module": "CMS Media",
            "status": "error",
            "message": "Media asset not found."
        }

    media_path = Path("/var/www/eternal-ledger-github") / asset.file_path.lstrip("/")
    thumb_path = None

    if asset.media_type == "image":
        thumb_name = f"{Path(asset.file_path).stem}.jpg"
        thumb_path = Path("/var/www/eternal-ledger-github/uploads/thumbnails") / thumb_name

    if media_path.exists():
        media_path.unlink()

    if thumb_path and thumb_path.exists():
        thumb_path.unlink()

    db.delete(asset)
    db.commit()

    return {
        "module": "CMS Media",
        "status": "deleted",
        "asset_id": asset_id
    }


@router.patch("/{asset_id}/status")
def update_media_asset_status(
    asset_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "editor"))
):
    asset = db.query(MediaAsset).filter(MediaAsset.id == asset_id).first()

    if not asset:
        return {
            "module": "CMS Media",
            "status": "error",
            "message": "Media asset not found."
        }

    allowed_statuses = ["draft", "reviewed", "published", "archived"]

    if status not in allowed_statuses:
        return {
            "module": "CMS Media",
            "status": "error",
            "message": "Invalid status.",
            "allowed_statuses": allowed_statuses
        }

    asset.status = status
    db.commit()
    db.refresh(asset)

    return {
        "module": "CMS Media",
        "status": "updated",
        "record": serialize_media_asset(asset)
    }
