from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.core.rate import limiter
import os

from app.core.config import settings
from app.api.v1.router import v1
from app.db.base import Base
from app.db.session import engine
import app.models.user, app.models.attendance, app.models.tracking, app.models.user_policy  # noqa

app = FastAPI(title=settings.APP_NAME)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
if settings.is_prod and settings.trusted_hosts != ["*"]:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_list,
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(v1)
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")


@app.on_event("startup")
def _startup():
    if settings.is_prod and settings.SECRET_KEY in ("change-me", "change-me-to-a-long-random-string"):
        raise RuntimeError("SECRET_KEY must be set to a long random value in prod")
    if not settings.is_prod:
        Base.metadata.create_all(bind=engine)  # dev convenience only; prod uses alembic
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


@app.get("/ready")
def ready():
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ready": True}
    except Exception as e:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content={"ready": False, "error": str(e)[:200]})
