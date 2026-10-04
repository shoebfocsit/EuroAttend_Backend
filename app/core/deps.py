from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.db.session import get_session
from app.core.security import decode
from app.models.user import User

bearer = HTTPBearer(auto_error=False)


def get_db():
    yield from get_session()


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if not creds:
        raise HTTPException(401, "Missing token")
    uid = decode(creds.credentials, "access")
    if not uid:
        raise HTTPException(401, "Invalid/expired token")
    u = db.get(User, uid)
    if not u or not u.is_active:
        raise HTTPException(401, "User inactive")
    return u


def require_admin(u: User = Depends(get_current_user)) -> User:
    if u.role != "admin":
        raise HTTPException(403, "Admin only")
    return u
