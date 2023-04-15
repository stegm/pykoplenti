import pytest
from unittest.mock import MagicMock, AsyncMock
from aiohttp import ClientResponse, ClientSession
from typing import Callable
import pykoplenti


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
def client_response_factory(websession_responses) -> Callable[[], MagicMock]:
    """Provides a factory to add responses to a ClientSession."""

    def factory():
        response = MagicMock(spec_set=ClientResponse, name="request Mock")
        websession_responses.append(response)
        return response

    return factory


@pytest.fixture
def pykoplenti_client(websession) -> pykoplenti.ApiClient:
    """Returns a pyokplent API-Client.

    The _login method is replaced with an AsyncMock.
    """
    client = pykoplenti.ApiClient(websession, "localhost")
    login_mock = AsyncMock()
    client._login = login_mock

    return client
