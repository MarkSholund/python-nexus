# PyNexus

A simple **FastAPI-based proxy server** for caching and serving Maven and PyPI artifacts locally. This service acts as a local cache for upstream repositories, reducing external requests and improving artifact availability.

---

## Features

- **Maven Proxy**
  - Serves artifacts from a local cache.
  - Fetches missing artifacts from [Maven Central](https://repo1.maven.org/maven2).
  - Returns appropriate HTTP status codes for missing or failed artifacts.

- **PyPI Proxy**
  - Serves package index (`simple/`) and JSON metadata (`/json`) from a local cache.
  - Caches actual package files under `packages/`.
  - Fetches missing packages from [PyPI](https://pypi.org).
  - Supports conditional GET with ETag and Last-Modified headers.

- **NPM Proxy**
  - Serves package metadata (registry JSON) and on-demand tarballs.
  - Metadata is cached under `cache/npm/...`; tarballs are fetched and cached when requested.
  - Fetches metadata and tarballs from `https://registry.npmjs.org`.
  - Scoped packages (e.g. `@scope/name`) are encoded when composing upstream URLs.

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
pip install -r requirements.txt
```

> Ensure `requirements.txt` includes at least:
>
> ```text
> fastapi
> uvicorn
> httpx
> beautifulsoup4
> ```

---

## Configuration

- **Upstream URLs**

```python
MAVEN_UPSTREAM = "https://repo1.maven.org/maven2"
PYPI_UPSTREAM = "https://pypi.org"
```

- **Local cache directories**

```python
from pathlib import Path
CACHE_DIR = Path("cache")  # or use environment variable
MAVEN_CACHE = CACHE_DIR / "maven"
PYPI_CACHE = CACHE_DIR / "pypi"
```

Ensure these directories exist and are writable by the application.

---

## Usage

Run the FastAPI server using **Uvicorn**:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Endpoints

- **Maven proxy**

```
GET /maven2/{groupId}/{artifactId}/{version}/{artifact}.jar
```

- **PyPI proxy**

```
GET /pypi/simple/                   # Root HTML index
GET /pypi/simple/{package}/          # Package index HTML
GET /pypi/{package}/json             # Package JSON metadata
GET /pypi/{package}/{version}/json   # Version-specific JSON
GET /pypi/packages/{path}            # Package files (wheel, tar, zip, etc.)

- **NPM proxy**

```
GET /npm/{package}                   # Package metadata JSON (cached)
GET /npm/{package}/-/{tarball}       # Package tarball (fetched on-demand)
POST /npm/-/npm/v1/security/advisories/bulk  # Proxies npm audit bulk requests (cached by body hash)
```
```

---

## Caching Behavior

- Files are served from the local cache if they exist.
- If a file is missing, it is downloaded, cached, and served.
- Supports **ETag** and **Last-Modified** headers for conditional GET requests.
- Upstream errors return proper HTTP status codes:
  - `404` for not found
  - `502` or upstream status code for other errors

- NPM-specific caching notes:
  - The server caches package metadata JSON under `cache/npm/{package}/index.json`.
  - Tarballs are not prefetched: requests to `/npm/{package}/-/{tarball}` fetch the tarball from the upstream registry and save it under `cache/npm/...`.

---

## Logging

- The app uses standard Python `logging`.
- You can configure the logging format using:

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(levelprefix)s %(asctime)s | %(message)s",
)
```

- The logs will show cache hits, upstream fetches, and errors.

---

## Environment Variables

- You can override cache directory with:

```bash
export NEXUS_CACHE_DIR=/path/to/cache
```

- Default is `cache`.

Notes on cache ownership and symlink safety

- The server enforces strict path containment for all cache operations. Key helpers are in `app/utils/utils.py`:
  - `safe_cache_path` validates and builds cache paths from user input.
  - `fetch_and_cache` verifies destinations are under the configured cache root and writes atomically (temp file + `os.replace`).
  - `conditional_file_response` re-resolves files before serving and supports conditional GETs (ETag / Last-Modified).

- For safety, run the service with a `NEXUS_CACHE_DIR` owned by the same user as the process and not writable by untrusted local users. This reduces symlink or replacement race risks.


---

## 🧪 Running Tests

Tests are written using **pytest** and include coverage reporting.

### 1. Install test dependencies

```bash
pip install -r test-requirements.txt
```

Your `test-requirements.txt` should include:

```text
-r requirements.txt
pytest
pytest-asyncio
pytest-cov
pytest-mock
```

### 2. Run all tests

```bash
PYTHONPATH=. pytest
```

### 3. Run tests with coverage summary

```bash
PYTHONPATH=. pytest --cov=app --cov-report=term-missing -v
```

### 4. Generate an HTML coverage report

```bash
PYTHONPATH=. pytest --cov=app --cov-report=html
```

Then open `htmlcov/index.html` in your browser to view detailed results.

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
# along with this program. If not, see <https://www.gnu.org/licenses/>
```

---

## Notes

- Recommended for internal artifact caching and proxying.
- Ensure cache directories have sufficient disk space for artifacts.
- Timeout for upstream requests:
  - Maven: 60 seconds
  - PyPI package files: 120 seconds
- Supports conditional GETs to reduce unnecessary bandwidth.