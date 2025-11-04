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

from urllib.parse import quote
from fastapi import APIRouter, HTTPException, Request
from app.config import config
from app.utils import utils

MAVEN_UPSTREAM = "https://repo1.maven.org/maven2"
MAVEN_CACHE = config.CACHE_DIR / "maven"

router = APIRouter(prefix="/maven2", tags=["Maven"])


@router.get("/{path:path}")
async def maven_proxy(path: str, request: Request):
    """
    Proxy Maven repository files, caching them under MAVEN_CACHE.
    Uses utils.safe_cache_path to prevent path traversal, and utils.fetch_and_cache
    which performs atomic writes and additional containment checks.
    """
    # Build a safe local cache path (rejects absolute paths / traversal)
    try:
        local_path = utils.safe_cache_path(MAVEN_CACHE, path)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path")

    # Fetch into cache if missing (fetch_and_cache will re-check containment)
    if not local_path.exists():
        upstream_url = f"{MAVEN_UPSTREAM}/{quote(path, safe='/')}"
        await utils.fetch_and_cache(upstream_url, local_path)

    # Serve the file (conditional_file_response re-validates containment before serving)
    try:
        return await utils.conditional_file_response(
            request, local_path, "application/octet-stream"
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404)
