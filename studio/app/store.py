"""Media storage adapters. Default is local disk. S3/MinIO is opt-in and never claimed live when unset."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from fastapi import HTTPException, status

from .config import Settings, get_settings
from .packzip import write_bytes

BACKEND_LOCAL = "local"
BACKEND_S3 = "s3"
KNOWN_MEDIA_BACKENDS = frozenset({BACKEND_LOCAL, BACKEND_S3})


class MediaStore(Protocol):
    backend: str

    def put(self, rel: str, data: bytes) -> None: ...

    def get_bytes(self, rel: str) -> bytes: ...

    def delete(self, rel: str) -> None: ...

    def exists(self, rel: str) -> bool: ...

    def local_path(self, rel: str) -> Path | None: ...


class LocalMediaStore:
    backend = BACKEND_LOCAL

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, rel: str) -> Path:
        relative = Path(rel)
        if relative.is_absolute() or ".." in relative.parts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Media path must be a relative store key.",
            )
        return self.root / relative

    def put(self, rel: str, data: bytes) -> None:
        write_bytes(self._path(rel), data)

    def get_bytes(self, rel: str) -> bytes:
        path = self._path(rel)
        if not path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Media file missing from the local store.",
            )
        return path.read_bytes()

    def delete(self, rel: str) -> None:
        path = self._path(rel)
        if path.is_file():
            path.unlink()

    def exists(self, rel: str) -> bool:
        return self._path(rel).is_file()

    def local_path(self, rel: str) -> Path | None:
        return self._path(rel)


class S3MediaStore:
    backend = BACKEND_S3

    def __init__(self, settings: Settings):
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:  # pragma: no cover - optional extra
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "STUDIO_MEDIA_BACKEND=s3 needs boto3. "
                    "Install with: pip install -e './studio[s3]'. "
                    "Unset the backend to stay on local disk."
                ),
            ) from exc
        bucket = (settings.s3_bucket or "").strip()
        if not bucket:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="STUDIO_MEDIA_BACKEND=s3 requires STUDIO_S3_BUCKET.",
            )
        endpoint = (settings.s3_endpoint or "").strip() or None
        region = (settings.s3_region or "us-east-1").strip() or "us-east-1"
        key_id = (settings.s3_access_key or "").strip() or None
        secret = (settings.s3_secret_key or "").strip() or None
        kwargs: dict = {"region_name": region}
        if endpoint:
            kwargs["endpoint_url"] = endpoint
            kwargs["config"] = Config(s3={"addressing_style": "path"})
        if key_id and secret:
            kwargs["aws_access_key_id"] = key_id
            kwargs["aws_secret_access_key"] = secret
        self.client = boto3.client("s3", **kwargs)
        self.bucket = bucket
        self.prefix = (settings.s3_prefix or "").strip().strip("/")

    def _key(self, rel: str) -> str:
        cleaned = str(rel).replace("\\", "/").lstrip("/")
        if ".." in Path(cleaned).parts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Media path must be a relative store key.",
            )
        if self.prefix:
            return f"{self.prefix}/{cleaned}"
        return cleaned

    def put(self, rel: str, data: bytes) -> None:
        self.client.put_object(Bucket=self.bucket, Key=self._key(rel), Body=data)

    def get_bytes(self, rel: str) -> bytes:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=self._key(rel))
        except Exception as exc:  # noqa: BLE001 — map missing objects to 404
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Media object missing from the S3/MinIO bucket.",
            ) from exc
        body = response.get("Body")
        return body.read() if body is not None else b""

    def delete(self, rel: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=self._key(rel))
        except Exception:
            return

    def exists(self, rel: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=self._key(rel))
            return True
        except Exception:
            return False

    def local_path(self, rel: str) -> Path | None:  # noqa: ARG002
        return None


def requested_backend(settings: Settings | None = None) -> str:
    cfg = settings or get_settings()
    raw = (cfg.media_backend or BACKEND_LOCAL).strip().lower()
    return raw if raw in KNOWN_MEDIA_BACKENDS else BACKEND_LOCAL


def s3_ready(settings: Settings | None = None) -> bool:
    cfg = settings or get_settings()
    return bool((cfg.s3_bucket or "").strip())


def active_backend(settings: Settings | None = None) -> str:
    """S3 is live only when requested *and* a bucket is set. Otherwise local, honestly."""
    cfg = settings or get_settings()
    if requested_backend(cfg) == BACKEND_S3 and s3_ready(cfg):
        return BACKEND_S3
    return BACKEND_LOCAL


def media_note(settings: Settings | None = None) -> str:
    cfg = settings or get_settings()
    wanted = requested_backend(cfg)
    live = active_backend(cfg)
    if live == BACKEND_S3:
        endpoint = (cfg.s3_endpoint or "").strip()
        where = f"endpoint {endpoint}" if endpoint else "default AWS endpoint"
        return (
            f"Object store ({where}, bucket={cfg.s3_bucket}). "
            "Sheets/zips only — not a generate bill and not a claim that cloud GPU ran."
        )
    if wanted == BACKEND_S3:
        return (
            "STUDIO_MEDIA_BACKEND requested s3 but STUDIO_S3_BUCKET is unset — staying on local disk. "
            "S3/MinIO is not live."
        )
    return f"Local disk under {cfg.media_root}. S3/MinIO is not live until backend=s3 and a bucket are set."


def get_store(settings: Settings | None = None) -> MediaStore:
    cfg = settings or get_settings()
    if active_backend(cfg) == BACKEND_S3:
        return S3MediaStore(cfg)
    return LocalMediaStore(cfg.media_path)
