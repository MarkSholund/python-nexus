# FastAPI Nexus Proxy

A simple **FastAPI-based proxy server** for caching and serving Maven and PyPI artifacts locally. This service acts as a local cache for upstream repositories, reducing external requests and improving artifact availability.

---

## Features

- **Maven Proxy**
  - Serves artifacts from a local cache.
  - Fetches missing artifacts from [Maven Central](https://repo1.maven.org/maven2) if upstream is enabled.
  - Returns appropriate HTTP status codes for missing or failed artifacts.

- **PyPI Proxy**
  - Serves package index (`simple/`) and JSON metadata (`/json`) from a local cache.
  - Caches actual package files under `packages/`.
  - Fetches missing packages from [PyPI](https://pypi.org) when upstream is enabled.


---

## Installation

1. **Clone the repository**

```bash
git clone <your-repo-url>
cd <repo-directory>
```

2. **Create a Python virtual environment**

```bash
python3 -m venv venv
source venv/bin/activate
```

3. **Install dependencies**

```bash
pip install fastapi httpx uvicorn
```

---

## Configuration

- **Upstream enabling/disabling**

```python
UPSTREAM_ENABLED = True
```

- **Upstream URLs**

```python
MAVEN_UPSTREAM = "https://repo1.maven.org/maven2"
PYPI_UPSTREAM = "https://pypi.org"
```

- **Local cache directories**

```python
CACHE_DIR = Path("~/.cache")
MAVEN_CACHE = CACHE_DIR / "maven"
PYPI_CACHE = CACHE_DIR / "pypi"
```

Ensure these directories exist and are writable by the application.

---

## Usage

Run the FastAPI server using **Uvicorn**:

```bash
uvicorn nexus:app --host 0.0.0.0 --port 8000
```

### Endpoints


- **Maven proxy**

```
GET /maven2/{groupId}/{artifactId}/{version}/{artifact}.jar
```

- **PyPI proxy**

```
GET /pypi/simple/{package}/         # HTML index
GET /pypi/{package}/json            # JSON metadata
GET /packages/{path}                # Package files
```

---

## Caching Behavior

- Files are served from the local cache if they exist.
- If a file is missing and upstream is enabled, it is downloaded, cached, and served.
- Upstream errors return proper HTTP status codes (`404` for not found, `502` for other errors).

---

## License

This project is licensed under the **GNU General Public License v3.0 (GPL-3.0)**.

- A copy of the full license is included in the `LICENSE` file.
- Include the following header in each source file:

```python
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
```

---

## Notes

- Recommended for internal artifact caching and proxying.
- Make sure cache directories have sufficient disk space for artifacts.
- Timeout for upstream requests:  
  - Maven: 60 seconds  
  - PyPI package files: 120 seconds

