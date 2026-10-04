from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext

from app.core.config import settings

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGO = "HS256"


def hash_password(pw: str) -> str:
    return pwd_ctx.hash(pw)


def verify_password(pw: str, hashed: str) -> bool:
    return pwd_ctx.verify(pw, hashed)


def _encode(sub: str, minutes: int = 0, days: int = 0, kind: str = "access") -> str:
    exp = datetime.utcnow() + (timedelta(minutes=minutes) if kind == "access" else timedelta(days=days))
    return jwt.encode({"sub": sub, "type": kind, "exp": exp}, settings.SECRET_KEY, algorithm=ALGO)


def create_access(user_id: int) -> str:
    return _encode(str(user_id), minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES, kind="access")


def create_refresh(user_id: int) -> str:
    return _encode(str(user_id), days=settings.REFRESH_TOKEN_EXPIRE_DAYS, kind="refresh")


def decode(token: str, expect: str = "access") -> int | None:
    try:
        p = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGO])
        if p.get("type") != expect:
            return None
        return int(p["sub"])
    except JWTError:
        return None
