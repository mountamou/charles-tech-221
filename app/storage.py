"""File storage backend: local disk (dev) or Cloudflare R2 (production).

Selected automatically from settings: R2 is used when the R2 credentials are
configured, otherwise files stay on local disk as before.
"""
from pathlib import Path
from typing import BinaryIO
import io
import shutil

from fastapi import HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from .config import settings

LOCAL_DIR = Path(settings.upload_dir) if settings.upload_dir else Path(__file__).parent / "uploads"
LOCAL_DIR.mkdir(parents=True, exist_ok=True)

_r2_client = None


def _using_r2() -> bool:
    return bool(settings.r2_account_id and settings.r2_access_key_id and settings.r2_secret_access_key and settings.r2_bucket)


def _r2():
    global _r2_client
    if _r2_client is None:
        import boto3
        _r2_client = boto3.client(
            "s3",
            endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
        )
    return _r2_client


def save(stored_name: str, fileobj: BinaryIO) -> None:
    if _using_r2():
        _r2().upload_fileobj(fileobj, settings.r2_bucket, stored_name)
    else:
        with (LOCAL_DIR / stored_name).open("wb") as out:
            shutil.copyfileobj(fileobj, out)


def download_response(stored_name: str, filename: str):
    if _using_r2():
        try:
            obj = _r2().get_object(Bucket=settings.r2_bucket, Key=stored_name)
        except Exception:
            raise HTTPException(404, "Fichier absent du stockage")
        return StreamingResponse(
            obj["Body"].iter_chunks(),
            media_type=obj.get("ContentType", "application/octet-stream"),
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    path = LOCAL_DIR / stored_name
    if not path.exists():
        raise HTTPException(404, "Fichier absent du stockage")
    return FileResponse(path, filename=filename)
