import os
from typing import Any, Callable, Union
from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientResponse, ClientSession
import pytest

import pykoplenti

only_smoketest: pytest.MarkDecorator = pytest.mark.skipif(
    os.getenv("SMOKETEST_HOST") is None, reason="Smoketest must be explicitly executed"
)


@pytest.fixture
def websession_responses() -> list[MagicMock]:
    """Provides a mutable list for responses of a ClientSession."""
    return []


@pytest.fixture
def websession(websession_responses) -> MagicMock:
    """Creates a mocked ClientSession.

    The client_response_factoryfixture can be used to add responses.
    """
    websession = MagicMock(spec_set=ClientSession, name="websession Mock")
    websession.request.return_value.__aenter__.side_effect = websession_responses
    return websession


@pytest.fixture
def client_response_factory(
    websession_responses,
) -> Callable[[int, Any], MagicMock]:
    """Provides a factory to add responses to a ClientSession."""

    def factory(status: int = 200, json: Union[list[Any], dict[Any, Any], None] = None):
        response = MagicMock(spec_set=ClientResponse, name="request Mock")
        response.status = status
        if json is not None:
            response.json.return_value = json

        websession_responses.append(response)
        return response

    return factory


@pytest.fixture
def pykoplenti_client(websession) -> pykoplenti.ApiClient:
    """Returns a pykoplenti API-Client.

    The _login method is replaced with an AsyncMock.
    """
    client = pykoplenti.ApiClient(websession, "localhost")
    login_mock = AsyncMock()
    client._login = login_mock  # type: ignore

    return client


@pytest.fixture
def pykoplenti_extended_client(websession) -> pykoplenti.ExtendedApiClient:
    """Returns a pykoplenti Extended API-Client.

    The _login method is replaced with an AsyncMock.
    """
    client = pykoplenti.ExtendedApiClient(websession, "localhost")
    login_mock = AsyncMock()
    client._login = login_mock  # type: ignore

    return client


@pytest.fixture
def smoketest_config() -> tuple[str, int, str]:
    """Return the configuration for smoke tests."""
    return (
        os.getenv("SMOKETEST_HOST", "localhost"),
        int(os.getenv("SMOKETEST_PORT", 80)),
        os.getenv("SMOKETEST_PASS", ""),
    )
