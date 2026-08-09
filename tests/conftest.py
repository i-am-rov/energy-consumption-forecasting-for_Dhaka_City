"""Shared fixtures for API and forecasting tests."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.main import app


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def metadata(client: TestClient) -> dict:
    response = client.get("/api/v1/metadata")
    assert response.status_code == 200
    return response.json()
