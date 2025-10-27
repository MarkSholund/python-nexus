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

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from pathlib import Path
import httpx
import gzip
import hashlib
import re
import email.utils as eut
from datetime import datetime, timezone

app = FastAPI()

# -------------------
# Configuration
# -------------------
UPSTREAM_ENABLED = True
MAVEN_UPSTREAM = "https://repo1.maven.org/maven2"
PYPI_UPSTREAM = "https://pypi.org"

CACHE_DIR = Path("cache")
MAVEN_CACHE = CACHE_DIR / "maven"
PYPI_CACHE = CACHE_DIR / "pypi"

# Compress files larger than this threshold (1MB)
COMPRESS_THRESHOLD = 1 * 1024 * 1024
COMPRESSED_EXT = ".gz"

# -------------------
# Utilities
# -------------------
def rewrite_index_html(html: str, base_url: str) -> str:
    """Rewrite href links in PyPI simple indexes to go through this proxy."""
    html = re.sub(
        r'href=["\']https://files\.pythonhosted\.org/([^"\']+)["\']',
        lambda m: f'href="{base_url}/packages/{m.group(1)}"',
        html,
    )
    html = re.sub(
        r'href=["\']https://pypi\.org/([^"\']+)["\']',
        lambda m: f'href="{base_url}/pypi/{m.group(1)}"',
        html,
    )
    return html


async def fetch_and_cache(url: str, dest: Path) -> Path:
    """Fetch remote resource and cache it locally (compress if large)."""
    gz_path = dest.with_suffix(dest.suffix + COMPRESSED_EXT)
    if dest.exists() or gz_path.exists():
        return dest

    if not UPSTREAM_ENABLED:
        raise HTTPException(status_code=404, detail=f"Offline and cache miss: {dest}")

    dest.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(follow_redirects=True, timeout=120.0) as client:
        r = await client.get(url)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=f"Upstream error: {url}")
        content = r.content

    # Compress if large
    if len(content) > COMPRESS_THRESHOLD:
        with gzip.open(gz_path, "wb") as f:
            f.write(content)
        return gz_path
    else:
        dest.write_bytes(content)
        return dest


def open_cached_file(path: Path) -> bytes:
    """Return bytes from cached file (decompressing if gzipped)."""
    gz_path = path.with_suffix(path.suffix + COMPRESSED_EXT)
    if path.exists():
        return path.read_bytes()
    elif gz_path.exists():
        with gzip.open(gz_path, "rb") as f:
            return f.read()
    raise FileNotFoundError(path)


def make_etag_and_last_modified(path: Path):
    """Generate ETag and Last-Modified headers from cached file metadata."""
    gz = path.with_suffix(path.suffix + COMPRESSED_EXT)
    if not path.exists() and gz.exists():
        path = gz
    if not path.exists():
        return None, None

    stat = path.stat()
    last_modified = eut.format_datetime(datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc))
    etag = hashlib.md5(f"{path.name}-{stat.st_size}-{stat.st_mtime}".encode()).hexdigest()
    return etag, last_modified


def file_headers(path: Path) -> dict:
    """Convenience wrapper to build consistent headers for any cached file."""
    etag, last_modified = make_etag_and_last_modified(path)
    headers = {}
    if etag:
        headers["ETag"] = etag
    if last_modified:
        headers["Last-Modified"] = last_modified
    return headers

# -------------------
# PyPI Routes
# -------------------

@app.get("/pypi/simple/")
async def pypi_root_index():
    """Cache and serve the root /simple/ index."""
    local_path = PYPI_CACHE / "simple" / "index.html"
    if not local_path.exists():
        if not UPSTREAM_ENABLED:
            raise HTTPException(status_code=404)
        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
            r = await client.get(f"{PYPI_UPSTREAM}/simple/")
            if r.status_code != 200:
                raise HTTPException(status_code=r.status_code)
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_text(r.text, encoding="utf-8")
    return FileResponse(local_path, media_type="text/html", headers=file_headers(local_path))


@app.get("/pypi/simple/{package}/")
async def pypi_package_index(package: str):
    """Serve /simple/{package}/ index and rewrite links."""
    local_path = PYPI_CACHE / "simple" / package / "index.html"
    if not local_path.exists():
        if not UPSTREAM_ENABLED:
            raise HTTPException(status_code=404)
        url = f"{PYPI_UPSTREAM}/simple/{package}/"
        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
            r = await client.get(url)
            if r.status_code != 200:
                raise HTTPException(status_code=r.status_code)
            rewritten = rewrite_index_html(r.text, base_url="/pypi")
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_text(rewritten, encoding="utf-8")
    return FileResponse(local_path, media_type="text/html", headers=file_headers(local_path))


@app.get("/pypi/packages/{path:path}")
async def pypi_artifact(path: str):
    """Serve cached .whl, .tar.gz, .zip, .metadata, etc."""
    local_path = PYPI_CACHE / "packages" / path
    if not (local_path.exists() or local_path.with_suffix(local_path.suffix + COMPRESSED_EXT).exists()):
        await fetch_and_cache(f"https://files.pythonhosted.org/{path}", local_path)
    try:
        data = open_cached_file(local_path)
        return Response(content=data, headers=file_headers(local_path))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Artifact not found in cache")


@app.get("/pypi/{package}/json")
async def pypi_package_json(package: str):
    """Cache and serve /pypi/{package}/json metadata."""
    local_path = PYPI_CACHE / package / "index.json"
    if not local_path.exists():
        await fetch_and_cache(f"{PYPI_UPSTREAM}/pypi/{package}/json", local_path)
    return FileResponse(local_path, media_type="application/json", headers=file_headers(local_path))


@app.get("/pypi/{package}/{version}/json")
async def pypi_package_version_json(package: str, version: str):
    """Cache and serve /pypi/{package}/{version}/json metadata."""
    local_path = PYPI_CACHE / package / version / "index.json"
    if not local_path.exists():
        await fetch_and_cache(f"{PYPI_UPSTREAM}/pypi/{package}/{version}/json", local_path)
    return FileResponse(local_path, media_type="application/json", headers=file_headers(local_path))

# -------------------
# Maven Routes
# -------------------

@app.get("/maven2/{path:path}")
async def maven_proxy(path: str):
    """Serve Maven artifacts with caching and headers."""
    local_path = MAVEN_CACHE / path
    if not (local_path.exists() or local_path.with_suffix(local_path.suffix + COMPRESSED_EXT).exists()):
        await fetch_and_cache(f"{MAVEN_UPSTREAM}/{path}", local_path)
    try:
        data = open_cached_file(local_path)
        return Response(content=data, headers=file_headers(local_path))
    except FileNotFoundError:
        raise HTTPException(status_code=404)

# -------------------
# Root
# -------------------

@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "Local caching proxy for PyPI and Maven with ETag, Last-Modified, and compression"
    }
