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

from app.config import config
from fastapi import APIRouter, HTTPException, Request
from app.utils import utils

MAVEN_UPSTREAM = "https://repo1.maven.org/maven2"
MAVEN_CACHE = config.CACHE_DIR / "maven"

router = APIRouter(prefix="/maven2")

# -------------------
# Maven Routes
# -------------------


@router.get("/{path:path}")
async def maven_proxy(path: str, request: Request):
    local_path = MAVEN_CACHE / path
    if not local_path.exists():
        await utils.fetch_and_cache(f"{MAVEN_UPSTREAM}/{path}", local_path)

    try:
        return await utils.conditional_file_response(request, local_path, "application/octet-stream")
    except FileNotFoundError:
        raise HTTPException(status_code=404)
