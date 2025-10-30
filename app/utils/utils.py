# SPDX-License-Identifier: GPL-3.0-or-later
#
# Copyright (C) 2025 Mark Sholund
#
# This file is part of the FastAPI Nexus Proxy project.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

from typing import Optional
from fastapi import HTTPException, Request, Response
from pathlib import Path
import httpx
import hashlib
from datetime import datetime


async def fetch_and_cache(url: str, dest: Path) -> Path:
    """Fetch remote resource and cache it locally (no compression)."""
    if dest.exists():
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(follow_redirects=True, timeout=120.0) as client:
        r = await client.get(url)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code,
                                detail=f"Upstream error: {url}")
        dest.write_bytes(r.content)
    return dest


def open_cached_file(path: Path) -> bytes:
    if path.exists():
        return path.read_bytes()
    raise FileNotFoundError(path)


def make_etag_and_last_modified(path: Path):
    stat = path.stat()
    etag = hashlib.sha256(
        f"{path.name}-{stat.st_mtime}-{stat.st_size}".encode("utf-8")).hexdigest()
    last_modified = datetime.utcfromtimestamp(  # type: ignore
        stat.st_mtime).strftime("%a, %d %b %Y %H:%M:%S GMT")
    return etag, last_modified


def file_headers(path: Path) -> dict:
    etag, last_modified = make_etag_and_last_modified(path)
    headers = {"ETag": etag, "Last-Modified": last_modified}
    return headers


async def conditional_file_response(
    request: Request,
    path: Path,
    media_type: str,
    attachment: Optional[bool] = False
) -> Response:
    """
    Return a FileResponse with ETag/Last-Modified headers and conditional GET support.

    If the client's If-None-Match or If-Modified-Since matches, return 304.
    """
    if not path.exists():
        raise FileNotFoundError(path)

    etag, last_modified = make_etag_and_last_modified(path)

    # Normalize headers (case-insensitive)
    if_none_match = request.headers.get(
        "if-none-match") or request.headers.get("If-None-Match")
    if_modified_since = request.headers.get(
        "if-modified-since") or request.headers.get("If-Modified-Since")

    if if_none_match == etag or if_modified_since == last_modified:
        return Response(status_code=304)

    headers = file_headers(path)
    if attachment:
        headers["Content-Disposition"] = f'attachment; filename="{path.name}"'

    content = open_cached_file(path)
    return Response(content=content, headers=headers, media_type=media_type)
