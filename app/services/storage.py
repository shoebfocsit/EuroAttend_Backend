"""S3-ready storage abstraction. Default: local ./uploads served statically."""
import os, uuid
from abc import ABC, abstractmethod

from app.core.config import settings


class StorageBackend(ABC):
    @abstractmethod
    def save(self, data: bytes, filename: str) -> str:
        """Save bytes, return public URL path."""


class LocalStorage(StorageBackend):
    def __init__(self, base_dir: str | None = None):
        self.base = base_dir or settings.UPLOAD_DIR
        os.makedirs(os.path.join(self.base, "selfies"), exist_ok=True)

    def save(self, data: bytes, filename: str) -> str:
        ext = os.path.splitext(filename)[1] or ".jpg"
        key = f"selfies/{uuid.uuid4().hex}{ext}"
        path = os.path.join(self.base, key)
        with open(path, "wb") as f:
            f.write(data)
        return f"/uploads/{key}"


class S3Storage(StorageBackend):
    """Stub — wire boto3 when STORAGE_BACKEND=s3."""
    def save(self, data: bytes, filename: str) -> str:
        raise NotImplementedError("Configure boto3 + S3_BUCKET to enable S3 storage")


def get_storage() -> StorageBackend:
    if settings.STORAGE_BACKEND == "s3":
        return S3Storage()
    return LocalStorage()
