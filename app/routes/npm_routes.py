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

from fastapi import APIRouter, HTTPException, Request
from pathlib import Path
from app.config import config
from app.utils import utils
from urllib.parse import quote
from http import HTTPMethod

NPM_UPSTREAM = "https://registry.npmjs.org"
NPM_CACHE = config.CACHE_DIR / "npm"

router = APIRouter(prefix="/npm", tags=["npm"])


# -------------------
# Helpers
# -------------------

def encode_scoped_package(pkg: str) -> str:
    """
    Encode scoped NPM packages correctly for upstream URLs.
    '@types/react' -> '%40types/react'
    'lodash' -> 'lodash'
    """
    if pkg.startswith("@") and "/" in pkg:
        scope, name = pkg.split("/", 1)
        return f"{quote(scope)}/{name}"
    return quote(pkg)


# -------------------
# NPM Routes
# -------------------

@router.get("/{package:path}")
async def npm_package_metadata(package: str, request: Request):
    """
    Serve package metadata (package.json-style).
    Example: GET /npm/lodash or /npm/@types/react
    Only cache metadata; do NOT prefetch tgz files.
    """
    local_path = NPM_CACHE / Path(*package.split("/")) / "index.json"

    if not local_path.exists():
        upstream_url = f"{NPM_UPSTREAM}/{encode_scoped_package(package)}"
        await utils.fetch_and_cache(upstream_url, local_path)

    try:
        return await utils.conditional_file_response(request, local_path, "application/json")
    except FileNotFoundError:
        raise HTTPException(status_code=404)


@router.get("/{package:path}/-/{tarball}")
async def npm_package_tarball(package: str, tarball: str, request: Request):
    """
    Serve tarball files on-demand.
    Example: GET /npm/lodash/-/lodash-4.17.21.tgz
             GET /npm/@types/react/-/react-18.2.21.tgz
    """
    local_path = NPM_CACHE / Path(*package.split("/")) / "-" / tarball

    if not local_path.exists():
        upstream_url = f"{NPM_UPSTREAM}/{encode_scoped_package(package)}/-/{quote(tarball)}"
        await utils.fetch_and_cache(upstream_url, local_path)

    try:
        return await utils.conditional_file_response(
            request, local_path, "application/octet-stream", attachment=True
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404)


@router.post("/-/npm/v1/security/advisories/bulk")
async def npm_security_bulk(request: Request):
    """
    Proxy npm audit bulk requests.
    Save response to cache based on a hash of the POST body.
    """
    body_bytes = await request.body()
    body_hash = str(abs(hash(body_bytes)))
    local_path = NPM_CACHE / "security" / f"{body_hash}.json"

    if local_path.exists():
        try:
            return await utils.conditional_file_response(request, local_path, "application/json")
        except FileNotFoundError:
            pass

    upstream_url = f"{NPM_UPSTREAM}/-/npm/v1/security/advisories/bulk"
    data = await utils.fetch_and_cache(upstream_url, local_path, method=HTTPMethod.POST, data=body_bytes)
    return data
