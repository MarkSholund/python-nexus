import pytest
from unittest.mock import AsyncMock, patch, mock_open
from pathlib import Path
import json
from datetime import datetime
from fastapi import Request
from fastapi.responses import Response
from app.utils import utils
from http import HTTPStatus
from app.utils.utils import HTTPMethod

# ------------------------
# open_cached_file
# ------------------------

def test_open_cached_file(tmp_path):
    file_path = tmp_path / "test.txt"
    file_path.write_bytes(b"hello")
    content = utils.open_cached_file(file_path)
    assert content == b"hello"

    missing_file = tmp_path / "missing.txt"
    with pytest.raises(FileNotFoundError):
        utils.open_cached_file(missing_file)

# ------------------------
# make_etag_and_last_modified
# ------------------------

def test_make_etag_and_last_modified(tmp_path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("abc")
    etag, last_modified = utils.make_etag_and_last_modified(file_path)
    assert isinstance(etag, str)
    assert isinstance(last_modified, str)
    assert len(etag) == 64  # sha256 hash length

# ------------------------
# file_headers
# ------------------------

def test_file_headers(tmp_path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("abc")
    headers = utils.file_headers(file_path)
    assert "ETag" in headers
    assert "Last-Modified" in headers

# ------------------------
# conditional_file_response
# ------------------------

@pytest.mark.asyncio
async def test_conditional_file_response_returns_content(tmp_path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("abc")

    request = AsyncMock()
    request.headers = {}

    response = await utils.conditional_file_response(request, file_path, "text/plain")
    assert isinstance(response, Response)
    assert response.status_code == 200
    assert response.body == b"abc"
    assert "ETag" in response.headers

@pytest.mark.asyncio
async def test_conditional_file_response_304(tmp_path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("abc")

    etag, last_modified = utils.make_etag_and_last_modified(file_path)

    request = AsyncMock()
    request.headers = {"If-None-Match": etag}

    response = await utils.conditional_file_response(request, file_path, "text/plain")
    assert response.status_code == 304

    request.headers = {"If-Modified-Since": last_modified}
    response = await utils.conditional_file_response(request, file_path, "text/plain")
    assert response.status_code == 304

# ------------------------
# fetch_and_cache
# ------------------------

@pytest.mark.asyncio
@patch("app.utils.utils.httpx.AsyncClient.get", new_callable=AsyncMock)
async def test_fetch_and_cache_get_bytes(mock_get, tmp_path):
    url = "http://example.com/data.txt"
    dest = tmp_path / "data.txt"

    mock_get.return_value.status_code = 200
    mock_get.return_value.content = b"abc"
    mock_get.return_value.text = "abc"

    result = await utils.fetch_and_cache(url, dest)
    assert dest.exists()
    assert dest.read_bytes() == b"abc"
    assert result == dest

@pytest.mark.asyncio
@patch("app.utils.utils.httpx.AsyncClient.post", new_callable=AsyncMock)
async def test_fetch_and_cache_post_json(mock_post, tmp_path):
    url = "http://example.com/api"
    dest = tmp_path / "resp.json"
    data = b'{"query":1}'

    mock_post.return_value.status_code = 200
    mock_post.return_value.text = '{"ok":true}'
    mock_post.return_value.content = b'{"ok":true}'

    result = await utils.fetch_and_cache(url, dest, method=HTTPMethod.POST, data=data, return_json=True)
    assert dest.exists()
    with open(dest) as f:
        saved = json.load(f)
    assert saved == {"ok": True}
    assert result == {"ok": True}

@pytest.mark.asyncio
@patch("app.utils.utils.httpx.AsyncClient.get", new_callable=AsyncMock)
async def test_fetch_and_cache_raises_http_exception(mock_get, tmp_path):
    url = "http://example.com/missing"
    dest = tmp_path / "missing.txt"

    class ResponseMock:
        status_code = 404
        def raise_for_status(self):
            raise utils.httpx.HTTPStatusError("Not Found", request=None, response=self)

    mock_get.return_value = ResponseMock()

    with pytest.raises(utils.HTTPException) as exc:
        await utils.fetch_and_cache(url, dest)
    assert exc.value.status_code == 404
