import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from pathlib import Path
from app.routes import npm_routes

client = TestClient(npm_routes.router)


@pytest.mark.asyncio
async def test_encode_scoped_package():
    # Scoped package
    assert npm_routes.encode_scoped_package("@types/react") == "%40types/react"
    # Normal package
    assert npm_routes.encode_scoped_package("lodash") == "lodash"


@pytest.mark.asyncio
@patch("app.routes.npm_routes.utils.conditional_file_response", new_callable=AsyncMock)
@patch("app.routes.npm_routes.utils.fetch_and_cache", new_callable=AsyncMock)
async def test_npm_package_metadata_fetch(mock_fetch, mock_response):
    test_package = "lodash"
    local_path = npm_routes.NPM_CACHE / Path(test_package) / "index.json"

    # File does not exist -> fetch_and_cache should be called
    with patch.object(Path, "exists", return_value=False):
        mock_response.return_value = {"name": "lodash"}
        response = await npm_routes.npm_package_metadata(test_package, request=AsyncMock())
        mock_fetch.assert_called_once()
        mock_response.assert_called_once()


@pytest.mark.asyncio
@patch("app.routes.npm_routes.utils.conditional_file_response", new_callable=AsyncMock)
@patch("app.routes.npm_routes.utils.fetch_and_cache", new_callable=AsyncMock)
async def test_npm_package_metadata_cached(mock_fetch, mock_response):
    test_package = "lodash"

    # File exists -> fetch_and_cache should NOT be called
    with patch.object(Path, "exists", return_value=True):
        mock_response.return_value = {"name": "lodash"}
        response = await npm_routes.npm_package_metadata(test_package, request=AsyncMock())
        mock_fetch.assert_not_called()
        mock_response.assert_called_once()


@pytest.mark.asyncio
@patch("app.routes.npm_routes.utils.conditional_file_response", new_callable=AsyncMock)
@patch("app.routes.npm_routes.utils.fetch_and_cache", new_callable=AsyncMock)
async def test_npm_package_tarball_fetch(mock_fetch, mock_response):
    test_package = "lodash"
    tarball = "lodash-4.17.21.tgz"

    # File does not exist -> fetch_and_cache should be called
    with patch.object(Path, "exists", return_value=False):
        mock_response.return_value = b"tarball content"
        response = await npm_routes.npm_package_tarball(test_package, tarball, request=AsyncMock())
        mock_fetch.assert_called_once()
        mock_response.assert_called_once()


@pytest.mark.asyncio
@patch("app.routes.npm_routes.utils.conditional_file_response", new_callable=AsyncMock)
@patch("app.routes.npm_routes.utils.fetch_and_cache", new_callable=AsyncMock)
async def test_npm_package_tarball_cached(mock_fetch, mock_response):
    test_package = "lodash"
    tarball = "lodash-4.17.21.tgz"

    # File exists -> fetch_and_cache should NOT be called
    with patch.object(Path, "exists", return_value=True):
        mock_response.return_value = b"cached tarball"
        response = await npm_routes.npm_package_tarball(test_package, tarball, request=AsyncMock())
        mock_fetch.assert_not_called()
        mock_response.assert_called_once()


@pytest.mark.asyncio
@patch("app.routes.npm_routes.utils.conditional_file_response", new_callable=AsyncMock)
@patch("app.routes.npm_routes.utils.fetch_and_cache", new_callable=AsyncMock)
async def test_npm_security_bulk_fetch(mock_fetch, mock_response):
    body = b'{"advisories":[]}'
    body_hash = str(abs(hash(body)))
    local_path = npm_routes.NPM_CACHE / "security" / f"{body_hash}.json"

    # File does not exist -> fetch_and_cache should be called
    with patch.object(Path, "exists", return_value=False):
        request_mock = AsyncMock()
        request_mock.body.return_value = body
        mock_fetch.return_value = {"result": "ok"}
        response = await npm_routes.npm_security_bulk(request_mock)
        mock_fetch.assert_called_once()
        assert response == {"result": "ok"}


@pytest.mark.asyncio
@patch("app.routes.npm_routes.utils.conditional_file_response", new_callable=AsyncMock)
async def test_npm_security_bulk_cached(mock_response):
    body = b'{"advisories":[]}'
    request_mock = AsyncMock()
    request_mock.body.return_value = body

    # File exists -> conditional_file_response should be called
    with patch.object(Path, "exists", return_value=True):
        mock_response.return_value = {"cached": True}
        response = await npm_routes.npm_security_bulk(request_mock)
        mock_response.assert_called_once()
        assert response == {"cached": True}


@pytest.mark.asyncio
async def test_npm_package_metadata_rejects_absolute_path():
    with pytest.raises(HTTPException) as exc_info:
        await npm_routes.npm_package_metadata("/etc/passwd", request=AsyncMock())
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_npm_package_tarball_rejects_traversal():
    with pytest.raises(HTTPException) as exc_info:
        await npm_routes.npm_package_tarball("../evil", "file.tgz", request=AsyncMock())
    assert exc_info.value.status_code == 400
