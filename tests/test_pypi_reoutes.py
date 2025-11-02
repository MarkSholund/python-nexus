import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock, patch
from pathlib import Path
from app.routes import pypi_routes

client = AsyncMock()


# -----------------------
# Helper function test
# -----------------------
def test_rewrite_index_html_relative_and_absolute():
    html = """
    <html>
      <body>
        <a href="https://files.pythonhosted.org/packages/abc.whl">whl</a>
        <a href="https://pypi.org/simple/package/">pkg</a>
        <a href="packages/xyz.tar.gz">tarball</a>
      </body>
    </html>
    """
    rewritten = pypi_routes.rewrite_index_html(html, base_url="/pypi")
    assert "/packages/abc.whl" in rewritten
    assert "/pypi/simple/package/" in rewritten
    assert "/packages/xyz.tar.gz" in rewritten


# -----------------------
# Tests for endpoints
# -----------------------

@pytest.mark.asyncio
@patch("app.routes.pypi_routes.utils.conditional_file_response", new_callable=AsyncMock)
@patch("app.routes.pypi_routes.httpx.AsyncClient.get", new_callable=AsyncMock)
async def test_pypi_root_index_fetch(mock_get, mock_response):
    # Simulate file does not exist
    with patch.object(Path, "exists", return_value=False):
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "<html>root index</html>"
        mock_response.return_value = b"content"

        request_mock = AsyncMock()
        response = await pypi_routes.pypi_root_index(request_mock)
        mock_response.assert_called_once()


@pytest.mark.asyncio
@patch("app.routes.pypi_routes.utils.conditional_file_response", new_callable=AsyncMock)
@patch("app.routes.pypi_routes.httpx.AsyncClient.get", new_callable=AsyncMock)
async def test_pypi_package_index_fetch(mock_get, mock_response):
    package = "example"
    with patch.object(Path, "exists", return_value=False):
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "<html><a href='packages/foo.whl'></a></html>"
        mock_response.return_value = b"content"

        request_mock = AsyncMock()
        response = await pypi_routes.pypi_package_index(package, request_mock)
        mock_response.assert_called_once()


@pytest.mark.asyncio
@patch("app.routes.pypi_routes.utils.conditional_file_response", new_callable=AsyncMock)
@patch("app.routes.pypi_routes.utils.fetch_and_cache", new_callable=AsyncMock)
async def test_pypi_artifact_fetch(mock_fetch, mock_response):
    path = "somepackage/file.whl"
    with patch.object(Path, "exists", return_value=False):
        mock_response.return_value = b"artifact"
        request_mock = AsyncMock()
        response = await pypi_routes.pypi_artifact(path, request_mock)
        mock_fetch.assert_called_once()
        mock_response.assert_called_once()


@pytest.mark.asyncio
@patch("app.routes.pypi_routes.utils.conditional_file_response", new_callable=AsyncMock)
@patch("app.routes.pypi_routes.utils.fetch_and_cache", new_callable=AsyncMock)
async def test_pypi_artifact_cached(mock_fetch, mock_response):
    path = "somepackage/file.whl"
    with patch.object(Path, "exists", return_value=True):
        mock_response.return_value = b"artifact"
        request_mock = AsyncMock()
        response = await pypi_routes.pypi_artifact(path, request_mock)
        mock_fetch.assert_not_called()
        mock_response.assert_called_once()


@pytest.mark.asyncio
@patch("app.routes.pypi_routes.utils.conditional_file_response", new_callable=AsyncMock)
@patch("app.routes.pypi_routes.utils.fetch_and_cache", new_callable=AsyncMock)
async def test_pypi_package_json_fetch(mock_fetch, mock_response):
    package = "example"
    with patch.object(Path, "exists", return_value=False):
        mock_response.return_value = {"json": True}
        request_mock = AsyncMock()
        response = await pypi_routes.pypi_package_json(package, request_mock)
        mock_fetch.assert_called_once()
        mock_response.assert_called_once()


@pytest.mark.asyncio
@patch("app.routes.pypi_routes.utils.conditional_file_response", new_callable=AsyncMock)
@patch("app.routes.pypi_routes.utils.fetch_and_cache", new_callable=AsyncMock)
async def test_pypi_package_version_json_fetch(mock_fetch, mock_response):
    package = "example"
    version = "1.0.0"
    with patch.object(Path, "exists", return_value=False):
        mock_response.return_value = {"json": True}
        request_mock = AsyncMock()
        response = await pypi_routes.pypi_package_version_json(package, version, request_mock)
        mock_fetch.assert_called_once()
        mock_response.assert_called_once()
