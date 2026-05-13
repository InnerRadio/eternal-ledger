from fastapi import APIRouter

router = APIRouter(prefix="/cms/memorials", tags=["CMS Memorials"])


@router.get("/")
def list_memorials():
    return {
        "module": "CMS Memorials",
        "status": "placeholder",
        "message": "Memorial archive listing endpoint planned.",
        "planned_records": [
            "companion memorials",
            "metadata endpoints",
            "media uploads",
            "XRPL verification records",
            "community stewardship selections"
        ]
    }


@router.get("/create")
def create_memorial_cms():
    return {
        "module": "CMS Memorials",
        "status": "placeholder",
        "message": "CMS memorial creation workflow planned."
    }
