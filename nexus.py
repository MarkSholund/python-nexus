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

from urllib.parse import urlparse
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from pathlib import Path
import httpx
import hashlib
from datetime import datetime

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

# -------------------
# Utilities
# -------------------


def rewrite_index_html(html: str, base_url: str) -> str:
    """Rewrite PyPI simple index links to route through proxy."""
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        orig = a["href"]
        parsed = urlparse(orig)
        new_href = orig  # default: unchanged

        if parsed.scheme in ("http", "https"):
            host = parsed.netloc.lower()
            if host.endswith("files.pythonhosted.org") and "/packages/" in parsed.path:
                suffix = parsed.path.split("/packages/", 1)[1]
                new_href = f"{base_url}/packages/{suffix}"
            elif host.endswith("pypi.org"):
                path = parsed.path.lstrip("/")
                new_href = f"{base_url}/{path}" if path else f"{base_url}/"
        else:
            # relative URL
            rel = orig.lstrip("/")
            if rel.startswith("packages/"):
                suffix = rel[len("packages/"):]
                new_href = f"{base_url}/packages/{suffix}"
            elif rel.startswith("pypi/"):
                new_href = f"{base_url}/{rel}"

        # preserve query and fragment
        if parsed.query:
            new_href += "?" + parsed.query
        if parsed.fragment:
            new_href += "#" + parsed.fragment

        a["href"] = new_href

    return str(soup)


async def fetch_and_cache(url: str, dest: Path) -> Path:
    """Fetch remote resource and cache it locally (no compression)."""
    if dest.exists():
        return dest
    if not UPSTREAM_ENABLED:
        raise HTTPException(
            status_code=404, detail=f"Offline and cache miss: {dest}")

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
    last_modified = datetime.utcfromtimestamp(
        stat.st_mtime).strftime("%a, %d %b %Y %H:%M:%S GMT")
    return etag, last_modified


def file_headers(path: Path) -> dict:
    etag, last_modified = make_etag_and_last_modified(path)
    headers = {"ETag": etag, "Last-Modified": last_modified}
    return headers

# -------------------
# PyPI Routes
# -------------------


@app.get("/nexus/ping.xml")
async def ping():
    return Response(content="""<?xml version="1.0" encoding="UTF-8"?>
<monitor>
    <service name="FastAPI Nexus">UP</service>
    <health>UP</health>
</monitor>
""", media_type="application/xml")


@app.get("/pypi/simple/")
async def pypi_root_index():
    local_path = PYPI_CACHE / "simple" / "index.html"
    if not local_path.exists():
        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
            r = await client.get(f"{PYPI_UPSTREAM}/simple/")
            if r.status_code != 200:
                raise HTTPException(status_code=r.status_code)
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_text(r.text, encoding="utf-8")
    return FileResponse(local_path, media_type="text/html", headers=file_headers(local_path))


@app.get("/pypi/simple/{package}/")
async def pypi_package_index(package: str):
    local_path = PYPI_CACHE / "simple" / package / "index.html"
    if not local_path.exists():
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
    local_path = PYPI_CACHE / "packages" / path
    if not local_path.exists():
        upstream_path = path
        if upstream_path.startswith("packages/"):
            upstream_path = upstream_path[len("packages/"):]
        await fetch_and_cache(f"https://files.pythonhosted.org/packages/{upstream_path}", local_path)

    try:
        data = open_cached_file(local_path)
        headers = file_headers(local_path)
        # Add content-disposition for wheels/archives
        if local_path.suffix in [".whl", ".zip", ".gz", ".tar"]:
            headers["Content-Disposition"] = f'attachment; filename="{local_path.name}"'
        return Response(content=data, headers=headers, media_type="application/octet-stream")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Artifact not found")


@app.get("/pypi/{package}/json")
async def pypi_package_json(package: str):
    local_path = PYPI_CACHE / package / "index.json"
    if not local_path.exists():
        await fetch_and_cache(f"{PYPI_UPSTREAM}/pypi/{package}/json", local_path)
    return FileResponse(local_path, media_type="application/json", headers=file_headers(local_path))


@app.get("/pypi/{package}/{version}/json")
async def pypi_package_version_json(package: str, version: str):
    local_path = PYPI_CACHE / package / version / "index.json"
    if not local_path.exists():
        await fetch_and_cache(f"{PYPI_UPSTREAM}/pypi/{package}/{version}/json", local_path)
    return FileResponse(local_path, media_type="application/json", headers=file_headers(local_path))

# -------------------
# Maven Routes
# -------------------


@app.get("/maven2/{path:path}")
async def maven_proxy(path: str):
    local_path = MAVEN_CACHE / path
    if not local_path.exists():
        await fetch_and_cache(f"{MAVEN_UPSTREAM}/{path}", local_path)
    try:
        data = open_cached_file(local_path)
        return Response(content=data, headers=file_headers(local_path), media_type="application/octet-stream")
    except FileNotFoundError:
        raise HTTPException(status_code=404)

# -------------------
# Root
# -------------------


@app.get("/")
async def root():
    return {"status": "ok", "message": "Local caching proxy for PyPI and Maven (no compression)"}
