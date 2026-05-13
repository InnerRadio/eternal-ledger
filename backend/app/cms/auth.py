from fastapi import APIRouter

router = APIRouter(prefix="/cms", tags=["CMS Auth"])


@router.get("/login")
def cms_login():
    return {
        "module": "CMS Auth",
        "status": "placeholder",
        "message": "CMS login endpoint planned for PurPaws and Eternal Ledger."
    }


@router.get("/register")
def cms_register():
    return {
        "module": "CMS Auth",
        "status": "placeholder",
        "message": "CMS registration endpoint planned."
    }
