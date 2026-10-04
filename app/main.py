from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter
from slowapi.util import get_remote_address
import os

from app.core.config import settings
from app.api.v1.router import v1
from app.db.base import Base
from app.db.session import engine
import app.models.user, app.models.attendance, app.models.tracking, app.models.user_policy  # noqa

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title=settings.APP_NAME)
app.state.limiter = limiter
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_list,
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(v1)
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")


@app.on_event("startup")
def _startup():
    Base.metadata.create_all(bind=engine)  # dev convenience; prod uses alembic
    try:
        from app.db.patch import ensure_columns
        ensure_columns()
    except Exception as e:
        print("column patch skipped:", e)
    if settings.AUTO_PUNCHOUT_ENABLED:
        try:
            from app.jobs.auto_punchout import start
            start()
        except Exception as e:
            print("scheduler skipped:", e)


@app.get("/health")
def health():
    return {"ok": True}
