from datetime import datetime
import json
from typing import Any, Callable
from unittest.mock import ANY, MagicMock

import pytest

import pykoplenti


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
        "description": "Reduction of AC power due to external command.",
        "category": "info",
        "is_active": false,
        "code": 5014,
        "end_time": "2023-04-29T00:45:19",
        "start_time": "2023-04-29T00:44:18",
        "group": "Information",
        "long_description": "Reduction of AC power due to external command."
    }"""

    event = pykoplenti.EventData(**json.loads(raw_response))

    assert event.start_time == datetime(2023, 4, 29, 0, 44, 18)
    assert event.end_time == datetime(2023, 4, 29, 0, 45, 19)
    assert event.is_active is False
    assert event.code == 5014
    assert event.long_description == "Reduction of AC power due to external command."
    assert event.category == "info"
    assert event.description == "Reduction of AC power due to external command."
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


def test_process_data_list():
    json = [
        {"id": "Statistic:Yield:Day", "unit": "%", "value": 1},
        {"id": "Statistic:Yield:Month", "unit": "%", "value": 2},
    ]

    assert pykoplenti.model.process_data_list(json) == [
        pykoplenti.ProcessData(id="Statistic:Yield:Day", unit="%", value="1"),
        pykoplenti.ProcessData(id="Statistic:Yield:Month", unit="%", value="2"),
    ]


def test_process_data_collection_indicates_length():
    raw_response = (
        '[{"id": "Statistic:Yield:Day", "unit": "", "value": 1}, '
        '{"id": "Statistic:Yield:Month", "unit": "", "value": 2}]'
    )
    pdc = pykoplenti.ProcessDataCollection(
        pykoplenti.model.process_data_list(json.loads(raw_response))
    )

    assert len(pdc) == 2


def test_process_data_collection_index_returns_processdata():
    raw_response = (
        '[{"id": "Statistic:Yield:Day", "unit": "", "value": 1}, '
        '{"id": "Statistic:Yield:Month", "unit": "", "value": 2}]'
    )
    pdc = pykoplenti.ProcessDataCollection(
        pykoplenti.model.process_data_list(json.loads(raw_response))
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
        pykoplenti.model.process_data_list(json.loads(raw_response))
    )

    result = list(pdc)

    assert result == ["Statistic:Yield:Day", "Statistic:Yield:Month"]


@pytest.mark.asyncio
async def test_relogin_on_401_response(
    pykoplenti_client: MagicMock,
    client_response_factory: Callable[[int, Any], MagicMock],
):
    """Ensures that a re-login is executed if a 401 response was returned."""

    # First response returns 401
    client_response_factory(401, None)

    # Second response is successfull
    client_response_factory(
        200,
        [
            {
                "moduleid": "moda",
                "processdata": [{"id": "procb", "unit": "", "value": 0}],
            }
        ],
    )

    _ = await pykoplenti_client.get_process_data_values("moda", "procb")

    pykoplenti_client._login.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_data_value(
    pykoplenti_client: MagicMock,
    client_response_factory: Callable[[int, Any], MagicMock],
    websession: MagicMock,
):
    """Test if process data values could be retrieved."""
    client_response_factory(
        200,
        [
            {
                "moduleid": "devices:local:pv1",
                "processdata": [
                    {"id": "P", "unit": "W", "value": 700.0},
                ],
            },
            {
                "moduleid": "devices:local:pv2",
                "processdata": [
                    {"id": "P", "unit": "W", "value": 300.0},
                ],
            },
        ],
    )

    values = await pykoplenti_client.get_process_data_values(
        {"devices:local:pv1": ["P"], "devices:local:pv2": ["P"]}
    )

    websession.request.assert_called_once_with(
        "POST",
        ANY,
        headers=ANY,
        json=[
            {"moduleid": "devices:local:pv1", "processdataids": ["P"]},
            {"moduleid": "devices:local:pv2", "processdataids": ["P"]},
        ],
    )

    assert values == {
        "devices:local:pv1": pykoplenti.ProcessDataCollection(
            [pykoplenti.ProcessData(id="P", unit="W", value=700.0)]
        ),
        "devices:local:pv2": pykoplenti.ProcessDataCollection(
            [pykoplenti.ProcessData(id="P", unit="W", value=300.0)]
        ),
    }
