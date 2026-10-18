from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.rate import limiter
from app.core.security import verify_password, create_access, create_refresh, decode
from app.models.user import User
from app.schemas.api import LoginIn, TokenOut, RefreshIn

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
@limiter.limit("10/minute")
def login(request: Request, body: LoginIn, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.mobile == body.mobile).first()
    if not u or not u.is_active or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Invalid mobile or password")
    return TokenOut(access_token=create_access(u.id), refresh_token=create_refresh(u.id))


@router.post("/refresh", response_model=TokenOut)
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    uid = decode(body.refresh_token, "refresh")
    if not uid:
        raise HTTPException(401, "Invalid refresh token")
    u = db.get(User, uid)
    if not u or not u.is_active:
        raise HTTPException(401, "User inactive")
    return TokenOut(access_token=create_access(u.id), refresh_token=create_refresh(u.id))
