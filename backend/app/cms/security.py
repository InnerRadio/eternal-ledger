from datetime import datetime, timedelta, timezone
import hashlib
import hmac

from jose import jwt

SECRET_KEY = "CHANGE_ME_TO_A_LONG_RANDOM_SECRET_BEFORE_PUBLIC_LAUNCH"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8


def get_password_hash(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return hmac.compare_digest(
        get_password_hash(plain_password),
        hashed_password
    )


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    return {
        "email": payload.get("sub"),
        "role": payload.get("role"),
        "user_id": payload.get("user_id")
    }


def require_roles(*allowed_roles):
    def role_checker(current_user = Depends(get_current_user)):
        user_role = current_user.get("role")

        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions."
            )

        return current_user

    return role_checker
