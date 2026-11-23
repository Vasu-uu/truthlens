"""Bounded upload reading shared by the image and audio routers."""
from __future__ import annotations

from fastapi import UploadFile

from app.main_errors import ApiError


async def read_limited(file: UploadFile | None, max_mb: int, kind: str) -> bytes:
    """Read an upload fully in memory, rejecting empty or oversize files.

    Nothing is written to disk, so there is nothing to clean up afterwards.
    """
    if file is None:
        raise ApiError(400, "missing_file", f"Please attach a {kind} file.")
    limit = max_mb * 1024 * 1024
    data = await file.read(limit + 1)
    await file.close()
    if not data:
        raise ApiError(400, "empty_file", f"The {kind} file is empty.")
    if len(data) > limit:
        raise ApiError(413, "file_too_large", f"The {kind} file is larger than {max_mb} MB.")
    return data
