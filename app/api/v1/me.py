from fastapi import APIRouter, Depends
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.api import UserOut

router = APIRouter(tags=["me"])


@router.get("/me", response_model=UserOut)
def me(u: User = Depends(get_current_user)):
    return u
