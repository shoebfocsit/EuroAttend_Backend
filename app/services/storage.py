"""S3-ready storage abstraction. Default: local ./uploads served statically."""
import os, uuid
from abc import ABC, abstractmethod

from app.core.config import settings


class StorageBackend(ABC):
    @abstractmethod
    def save(self, data: bytes, filename: str) -> str:
        """Save bytes, return public URL path."""


class LocalStorage(StorageBackend):
    ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
    MAX_BYTES = 5 * 1024 * 1024

    def __init__(self, base_dir: str | None = None):
        self.base = base_dir or settings.UPLOAD_DIR
        os.makedirs(os.path.join(self.base, "selfies"), exist_ok=True)

    def save(self, data: bytes, filename: str) -> str:
        if not data or len(data) > self.MAX_BYTES:
            raise ValueError("Selfie too large (max 5MB)")
        ext = os.path.splitext(filename)[1].lower() or ".jpg"
        if ext not in self.ALLOWED_EXTS:
            raise ValueError(f"Selfie type not allowed: {ext}")
        # magic-byte sniff: reject non-images masquerading as .jpg
        head = data[:12]
        is_jpeg = head[:2] == b"\xff\xd8"
        is_png = head[:8] == b"\x89PNG\r\n\x1a\n"
        is_webp = head[:4] == b"RIFF" and data[8:12] == b"WEBP"
        if not (is_jpeg or is_png or is_webp):
            raise ValueError("File is not a valid image (JPEG/PNG/WEBP only)")
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
