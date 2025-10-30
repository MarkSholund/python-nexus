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
from fastapi import APIRouter, HTTPException, Request
import httpx
from app.config import config
from app.utils import utils

router = APIRouter(prefix="/pypi", tags=["PyPI"])

PYPI_UPSTREAM = "https://pypi.org"
PYPI_CACHE = config.CACHE_DIR / "pypi"


def rewrite_index_html(html: str, base_url: str) -> str:
    """Rewrite PyPI simple index links to route through proxy."""
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        orig = a["href"]
        parsed = urlparse(orig)  # type: ignore
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
            rel = orig.lstrip("/")  # type: ignore
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


@router.get("/simple/")
async def pypi_root_index(request: Request):
    local_path = PYPI_CACHE / "simple" / "index.html"
    if not local_path.exists():
        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
            r = await client.get(f"{PYPI_UPSTREAM}/simple/")
            if r.status_code != 200:
                raise HTTPException(status_code=r.status_code)
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_text(r.text, encoding="utf-8")

    return await utils.conditional_file_response(request, local_path, "text/html")


@router.get("/simple/{package}/")
async def pypi_package_index(package: str, request: Request):
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

    return await utils.conditional_file_response(request, local_path, "text/html")


@router.get("/packages/{path:path}")
async def pypi_artifact(path: str, request: Request):
    local_path = PYPI_CACHE / "packages" / path
    if not local_path.exists():
        upstream_path = path
        if upstream_path.startswith("packages/"):
            upstream_path = upstream_path[len("packages/"):]
        await utils.fetch_and_cache(f"https://files.pythonhosted.org/packages/{upstream_path}", local_path)

    try:
        attachment = local_path.suffix in [".whl", ".zip", ".gz", ".tar"]
        return await utils.conditional_file_response(request, local_path, "application/octet-stream", attachment=attachment)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Artifact not found")


@router.get("/{package}/json")
async def pypi_package_json(package: str, request: Request):
    local_path = PYPI_CACHE / package / "index.json"
    if not local_path.exists():
        await utils.fetch_and_cache(f"{PYPI_UPSTREAM}/pypi/{package}/json", local_path)

    return await utils.conditional_file_response(request, local_path, "application/json")


@router.get("/{package}/{version}/json")
async def pypi_package_version_json(package: str, version: str, request: Request):
    local_path = PYPI_CACHE / package / version / "index.json"
    if not local_path.exists():
        await utils.fetch_and_cache(f"{PYPI_UPSTREAM}/pypi/{package}/{version}/json", local_path)

    return await utils.conditional_file_response(request, local_path, "application/json")
