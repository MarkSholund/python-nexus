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
from app.config import config
from app.utils import utils

NPM_UPSTREAM = "https://registry.npmjs.org"
NPM_CACHE = config.CACHE_DIR / "npm"

router = APIRouter(prefix="/npm", tags=["NPM"])

# -------------------
# NPM Routes
# -------------------


@router.get("/{package_name}")
async def npm_package_metadata(package_name: str, request: Request):
    """
    Serve and cache npm package metadata (package.json-style).
    Example: /npm/react
    """
    local_path = NPM_CACHE / f"{package_name}.json"
    upstream_url = f"{NPM_UPSTREAM}/{package_name}"

    if not local_path.exists():
        await utils.fetch_and_cache(upstream_url, local_path)

    try:
        return await utils.conditional_file_response(request, local_path, "application/json")
    except FileNotFoundError:
        raise HTTPException(status_code=404)


@router.get("/{package_name}/-/{tarball}")
async def npm_tarball(package_name: str, tarball: str, request: Request):
    """
    Serve and cache npm tarballs (.tgz)
    Example: /npm/react/-/react-18.2.0.tgz
    """
    local_path = NPM_CACHE / package_name / "-" / tarball
    upstream_url = f"{NPM_UPSTREAM}/{package_name}/-/{tarball}"

    if not local_path.exists():
        await utils.fetch_and_cache(upstream_url, local_path)

    try:
        return await utils.conditional_file_response(request, local_path, "application/gzip")
    except FileNotFoundError:
        raise HTTPException(status_code=404)
