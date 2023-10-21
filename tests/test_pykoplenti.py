from datetime import datetime
import os
import re
from typing import AsyncGenerator
import aiohttp

import pytest
import pytest_asyncio
import pykoplenti
import json
from pydantic import parse_obj_as


def test_me_parsing():
    raw_response = """\
    {
        "role": "NONE",
        "anonymous": true,
        "locked": false,
        "permissions": [],
        "active": false,
        "authenticated": false
    }"""

    me = pykoplenti.MeData(**json.loads(raw_response))

    assert me.is_locked is False
    assert me.is_active is False
    assert me.is_authenticated is False
    assert me.permissions == []
    assert me.is_anonymous is True
    assert me.role == "NONE"


def test_version_parsing():
    raw_response = """\
    {
        "sw_version": "01.26.09454",
        "name": "PUCK RESTful API",
        "api_version": "0.2.0",
        "hostname": "scb"
    }"""

    version = pykoplenti.VersionData(**json.loads(raw_response))

    assert version.api_version == "0.2.0"
    assert version.hostname == "scb"
    assert version.name == "PUCK RESTful API"
    assert version.sw_version == "01.26.09454"


def test_event_parsing():
    raw_response = """\
    {
        "description": "Reduction of AC power due to external command or high grid frequency.",
        "category": "info",
        "is_active": false,
        "code": 5014,
        "end_time": "2023-04-29T00:45:19",
        "start_time": "2023-04-29T00:44:18",
        "group": "Information",
        "long_description": "Reduction of AC power due to external command or high grid frequency."
    }"""

    event = pykoplenti.EventData(**json.loads(raw_response))

    assert event.start_time == datetime(2023, 4, 29, 0, 44, 18)
    assert event.end_time == datetime(2023, 4, 29, 0, 45, 19)
    assert event.is_active is False
    assert event.code == 5014
    assert (
        event.long_description
        == "Reduction of AC power due to external command or high grid frequency."
    )
    assert event.category == "info"
    assert (
        event.description
        == "Reduction of AC power due to external command or high grid frequency."
    )
    assert event.group == "Information"


def test_module_parsing():
    raw_response = """\
    {
        "id": "devices:local:powermeter",
        "type": "device:powermeter"
    }"""

    module = pykoplenti.ModuleData(**json.loads(raw_response))

    assert module.id == "devices:local:powermeter"
    assert module.type == "device:powermeter"


def test_process_parsing():
    raw_response = """\
    {
        "id": "Inverter:State",
        "unit": "",
        "value": 6
    }"""

    process_data = pykoplenti.ProcessData(**json.loads(raw_response))

    assert process_data.id == "Inverter:State"
    assert process_data.unit == ""
    assert process_data.value == 6


def test_settings_parsing():
    raw_response = """\
    {
        "min": "0",
        "default": null,
        "access": "readonly",
        "unit": null,
        "id": "Properties:PowerId",
        "type": "uint32",
        "max": "100000"
    }"""

    settings_data = pykoplenti.SettingsData(**json.loads(raw_response))

    assert settings_data.unit is None
    assert settings_data.default is None
    assert settings_data.id == "Properties:PowerId"
    assert settings_data.max == "100000"
    assert settings_data.min == "0"
    assert settings_data.type == "uint32"
    assert settings_data.access == "readonly"


def test_process_data_collection_indicates_length():
    raw_response = (
        '[{"id": "Statistic:Yield:Day", "unit": "", "value": 1}, '
        '{"id": "Statistic:Yield:Month", "unit": "", "value": 2}]'
    )
    pdc = pykoplenti.ProcessDataCollection(
        parse_obj_as(list[pykoplenti.ProcessData], json.loads(raw_response))
    )

    assert len(pdc) == 2


def test_process_data_collection_index_returns_processdata():
    raw_response = (
        '[{"id": "Statistic:Yield:Day", "unit": "", "value": 1}, '
        '{"id": "Statistic:Yield:Month", "unit": "", "value": 2}]'
    )
    pdc = pykoplenti.ProcessDataCollection(
        parse_obj_as(list[pykoplenti.ProcessData], json.loads(raw_response))
    )

    result = pdc["Statistic:Yield:Month"]

    assert isinstance(result, pykoplenti.ProcessData)
    assert result.id == "Statistic:Yield:Month"
    assert result.unit == ""
    assert result.value == 2


def test_process_data_collection_can_be_iterated():
    raw_response = (
        '[{"id": "Statistic:Yield:Day", "unit": "", "value": 1}, '
        '{"id": "Statistic:Yield:Month", "unit": "", "value": 2}]'
    )
    pdc = pykoplenti.ProcessDataCollection(
        parse_obj_as(list[pykoplenti.ProcessData], json.loads(raw_response))
    )

    result = list(pdc)

    assert len(result) == 2
    assert result[0].id == "Statistic:Yield:Day"
    assert result[1].id == "Statistic:Yield:Month"


@pytest.mark.asyncio
async def test_relogin_on_401_response(
    pykoplenti_client: pykoplenti.ApiClient, client_response_factory
):
    """Ensures that a re-login is executed if a 401 response was returned."""

    # First response returns 401
    response1 = client_response_factory()
    response1.status = 401

    # Second response is successfull
    response2 = client_response_factory()
    response2.status = 200
    response2.json.return_value = [
        {"moduleid": "moda", "processdata": [{"id": "procb", "unit": "", "value": 0}]}
    ]

    _ = await pykoplenti_client.get_process_data_values("moda", "procb")

    pykoplenti_client._login.assert_awaited_once()


@pytest_asyncio.fixture
async def authenticated_client() -> AsyncGenerator[pykoplenti.ApiClient, None]:
    host = os.getenv("SMOKETEST_HOST")
    port = int(os.getenv("SMOKETEST_PORT"))
    password = os.getenv("SMOKETEST_PASS")

    async with aiohttp.ClientSession() as session:
        client = pykoplenti.ApiClient(session, host, port)
        await client.login(password)
        yield client
        await client.logout()


@pytest.mark.skipif(
    os.getenv("SMOKETEST_HOST") is None, reason="Smoketest must be explicitly executed"
)
class TestSmokeTests:
    """Contains smoke tests which are executed on a real inverter.

    This tests are not automatically executed because they need real HW. Please
    note that all checks are highl volatile because of different configuration and
    firmware version of the inverter.
    """

    @pytest.mark.asyncio
    async def test_smoketest_me(self, authenticated_client: pykoplenti.ApiClient):
        """Retrieves the MeData."""

        me = await authenticated_client.get_me()

        assert me == pykoplenti.MeData(
            locked=False,
            active=True,
            authenticated=True,
            permissions=[],
            anonymous=False,
            role="USER",
        )

    @pytest.mark.asyncio
    async def test_smoketest_version(self, authenticated_client: pykoplenti.ApiClient):
        """Retrieves the VersionData."""

        version = await authenticated_client.get_version()

        # version info are highly variable hence only some basic checks are performed
        assert len(version.hostname) > 0
        assert len(version.name) > 0
        assert re.match("\d+.\d+.\d+", version.api_version) is not None
        assert re.match("\d+.\d+.\d+", version.sw_version) is not None

    @pytest.mark.asyncio
    async def test_smoketest_modules(self, authenticated_client: pykoplenti.ApiClient):
        """Retrieves the ModuleData."""

        modules = await authenticated_client.get_modules()

        assert len(modules) >= 17
        assert pykoplenti.ModuleData(id="devices:local", type="device") in modules

    @pytest.mark.asyncio
    async def test_smoketest_settings(self, authenticated_client: pykoplenti.ApiClient):
        """Retrieves the SettingsData."""

        settings = await authenticated_client.get_settings()

        assert "devices:local" in settings
        assert (
            pykoplenti.SettingsData(
                min="0",
                max="32",
                default=None,
                access="readonly",
                unit=None,
                id="Branding:ProductName1",
                type="string",
            )
            in settings["devices:local"]
        )

    @pytest.mark.asyncio
    async def test_smoketest_setting_value1(
        self, authenticated_client: pykoplenti.ApiClient
    ):
        """Retrieves the setting value with variante 1."""

        setting_value = await authenticated_client.get_setting_values(
            "devices:local", "Branding:ProductName1"
        )

        assert setting_value == {
            "devices:local": {"Branding:ProductName1": "PLENTICORE plus"}
        }

    @pytest.mark.asyncio
    async def test_smoketest_setting_value2(
        self, authenticated_client: pykoplenti.ApiClient
    ):
        """Retrieves the setting value with variante 2."""

        setting_value = await authenticated_client.get_setting_values(
            "devices:local", ["Branding:ProductName1"]
        )

        assert setting_value == {
            "devices:local": {"Branding:ProductName1": "PLENTICORE plus"}
        }

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="API endpoint is not working")
    async def test_smoketest_setting_value3(
        self, authenticated_client: pykoplenti.ApiClient
    ):
        """Retrieves the setting value with variante 3."""

        setting_value = await authenticated_client.get_setting_values(
            "devices:local", None
        )

        assert (
            setting_value["devices:local"]["Branding:ProductName1"] == "PLENTICORE plus"
        )

    @pytest.mark.asyncio
    async def test_smoketest_setting_value4(
        self, authenticated_client: pykoplenti.ApiClient
    ):
        """Retrieves the setting value with variante 4."""

        setting_value = await authenticated_client.get_setting_values(
            {"devices:local": ["Branding:ProductName1"]}
        )

        assert setting_value == {
            "devices:local": {"Branding:ProductName1": "PLENTICORE plus"}
        }

    @pytest.mark.asyncio
    async def test_smoketest_process_data_value1(
        self, authenticated_client: pykoplenti.ApiClient
    ):
        """Retrieves process data values by using str, str variant."""
        process_data = await authenticated_client.get_process_data_values(
            "devices:local", "EM_State"
        )

        assert process_data.keys() == {"devices:local"}
        assert len(process_data["devices:local"]) == 1
        assert process_data["devices:local"]["EM_State"] is not None

    @pytest.mark.asyncio
    async def test_smoketest_process_data_value2(
        self, authenticated_client: pykoplenti.ApiClient
    ):
        """Retrieves process data values by using str, Iterable[str] variant."""
        process_data = await authenticated_client.get_process_data_values(
            "devices:local", ["EM_State", "Inverter:State"]
        )

        assert process_data.keys() == {"devices:local"}
        assert len(process_data["devices:local"]) == 2
        assert process_data["devices:local"]["EM_State"] is not None
        assert process_data["devices:local"]["Inverter:State"] is not None

    @pytest.mark.asyncio
    async def test_smoketest_process_data_value3(
        self, authenticated_client: pykoplenti.ApiClient
    ):
        """Retrieves process data values by using Dict[str, Iterable[str]] variant."""
        process_data = await authenticated_client.get_process_data_values(
            {
                "devices:local": ["EM_State", "Inverter:State"],
                "scb:export": ["PortalConActive"],
            }
        )

        assert process_data.keys() == {"devices:local", "scb:export"}
        assert len(process_data["devices:local"]) == 2
        assert process_data["devices:local"]["EM_State"] is not None
        assert process_data["devices:local"]["Inverter:State"] is not None
        assert len(process_data["scb:export"]) == 1
        assert process_data["scb:export"]["PortalConActive"] is not None
