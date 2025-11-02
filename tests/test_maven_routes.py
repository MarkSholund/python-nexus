import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from pathlib import Path
from app.routes import maven_routes

client = TestClient(maven_routes.router)

@pytest.mark.asyncio
@patch("app.routes.maven_routes.utils.conditional_file_response", new_callable=AsyncMock)
@patch("app.routes.maven_routes.utils.fetch_and_cache", new_callable=AsyncMock)
async def test_maven_proxy_fetch(mock_fetch, mock_response):
    """
    Test fetching a file when local cache does not exist
    """
    test_path = "com/example/test/1.0/test-1.0.jar"
    local_path = maven_routes.MAVEN_CACHE / test_path

    # Patch Path.exists to simulate file missing
    with patch.object(Path, "exists", return_value=False):
        mock_response.return_value = b"file content"
        response = await maven_routes.maven_proxy(test_path, request=AsyncMock())
        # Ensure fetch_and_cache is called since file does not exist
        mock_fetch.assert_called_once_with(f"{maven_routes.MAVEN_UPSTREAM}/{test_path}", local_path)
        mock_response.assert_called_once()


@pytest.mark.asyncio
@patch("app.routes.maven_routes.utils.conditional_file_response", new_callable=AsyncMock)
@patch("app.routes.maven_routes.utils.fetch_and_cache", new_callable=AsyncMock)
async def test_maven_proxy_cached(mock_fetch, mock_response):
    """
    Test fetching a file that exists in local cache
    """
    test_path = "com/example/test/1.0/test-1.0.jar"
    local_path = maven_routes.MAVEN_CACHE / test_path

    # File exists -> fetch_and_cache should NOT be called
    with patch.object(Path, "exists", return_value=True):
        mock_response.return_value = b"cached content"
        response = await maven_routes.maven_proxy(test_path, request=AsyncMock())
        mock_fetch.assert_not_called()
        mock_response.assert_called_once()


@pytest.mark.asyncio
@patch("app.routes.maven_routes.utils.conditional_file_response", new_callable=AsyncMock)
@patch("app.routes.maven_routes.utils.fetch_and_cache", new_callable=AsyncMock)
async def test_maven_proxy_file_not_found(mock_fetch, mock_response):
    """
    Test that a FileNotFoundError inside conditional_file_response
    raises HTTPException with 404 status code
    """
    test_path = "com/example/missing/1.0/missing-1.0.jar"

    # File exists, but conditional_file_response raises FileNotFoundError
    with patch.object(Path, "exists", return_value=True):
        mock_response.side_effect = FileNotFoundError
        with pytest.raises(HTTPException) as exc_info:
            await maven_routes.maven_proxy(test_path, request=AsyncMock())
        # Assert status code is 404
        assert exc_info.value.status_code == 404