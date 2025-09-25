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

app = FastAPI()

# Upstreams
UPSTREAM_ENABLED = True
MAVEN_UPSTREAM = "https://repo1.maven.org/maven2"
PYPI_UPSTREAM = "https://pypi.org"

# Cache dirs
CACHE_DIR = Path("./cache")
MAVEN_CACHE = CACHE_DIR / "maven"
PYPI_CACHE = CACHE_DIR / "pypi"


# -------------------
# Maven Proxy
# -------------------
@app.get("/maven2/{full_path:path}")
async def proxy_maven(full_path: str):
    local_path = MAVEN_CACHE / full_path
    if local_path.exists():
        return FileResponse(local_path)

    if UPSTREAM_ENABLED:
        upstream_url = f"{MAVEN_UPSTREAM}/{full_path}"
        local_path.parent.mkdir(parents=True, exist_ok=True)

        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
            try:
                r = await client.get(upstream_url)
            except httpx.RequestError:
                raise HTTPException(
                    status_code=502, detail="Upstream request failed")

            if r.status_code == 200:
                local_path.write_bytes(r.content)
                return FileResponse(local_path, media_type=r.headers.get("content-type"))
            elif r.status_code == 404:
                raise HTTPException(
                    status_code=404, detail="Artifact not found")
            else:
                raise HTTPException(
                    status_code=502, detail=f"Upstream error {r.status_code}")
    else:
        raise HTTPException(status_code=404, detail="Artifact not found")

# -------------------
# PyPI Proxy
# -------------------


@app.get("/pypi/simple/{package}/")
async def proxy_pypi_simple(package: str):
    local_path = PYPI_CACHE / "simple" / package / "index.html"
    if local_path.exists():
        return FileResponse(local_path, media_type="text/html")

    if UPSTREAM_ENABLED:
        upstream_url = f"{PYPI_UPSTREAM}/simple/{package}/"
        async with httpx.AsyncClient(follow_redirects=True) as client:
            r = await client.get(upstream_url)
            if r.status_code == 200:
                local_path.parent.mkdir(parents=True, exist_ok=True)
                local_path.write_text(r.text, encoding="utf-8")
                return Response(r.text, media_type="text/html")
            elif r.status_code == 404:
                raise HTTPException(
                    status_code=404, detail="Package not found")
            else:
                raise HTTPException(
                    status_code=502, detail=f"Upstream error {r.status_code}")
    else:
        raise HTTPException(status_code=404, detail="Artifact not found")


@app.get("/pypi/{package}/json")
async def proxy_pypi_json(package: str):
    local_path = PYPI_CACHE / "json" / f"{package}.json"
    if local_path.exists():
        return FileResponse(local_path, media_type="application/json")

    if UPSTREAM_ENABLED:
        upstream_url = f"{PYPI_UPSTREAM}/pypi/{package}/json"
        async with httpx.AsyncClient(follow_redirects=True) as client:
            r = await client.get(upstream_url)
            if r.status_code == 200:
                local_path.parent.mkdir(parents=True, exist_ok=True)
                local_path.write_text(r.text, encoding="utf-8")
                return Response(r.text, media_type="application/json")
            elif r.status_code == 404:
                raise HTTPException(
                    status_code=404, detail="Package not found")
            else:
                raise HTTPException(
                    status_code=502, detail=f"Upstream error {r.status_code}")
    else:
        raise HTTPException(status_code=404, detail="Artifact not found")


@app.get("/packages/{path:path}")
async def proxy_pypi_package(path: str):
    local_path = PYPI_CACHE / "packages" / path
    if local_path.exists():
        return FileResponse(local_path)

    if UPSTREAM_ENABLED:
        upstream_url = f"{PYPI_UPSTREAM}/packages/{path}"
        local_path.parent.mkdir(parents=True, exist_ok=True)
        async with httpx.AsyncClient(follow_redirects=True, timeout=120.0) as client:
            r = await client.get(upstream_url)
            if r.status_code == 200:
                local_path.write_bytes(r.content)
                return FileResponse(local_path, media_type=r.headers.get("content-type"))
            elif r.status_code == 404:
                raise HTTPException(status_code=404, detail="File not found")
            else:
                raise HTTPException(
                    status_code=502, detail=f"Upstream error {r.status_code}")
    else:
        raise HTTPException(status_code=404, detail="Artifact not found")
