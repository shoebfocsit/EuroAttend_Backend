from fastapi import APIRouter
from app.api.v1 import auth, me, attendance, tracking, admin

v1 = APIRouter(prefix="/api/v1")
v1.include_router(auth.router)
v1.include_router(me.router)
v1.include_router(attendance.router)
v1.include_router(tracking.router)
v1.include_router(admin.router)
