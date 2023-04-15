from datetime import datetime

import pytest
import pykoplenti
import json


def test_me_parsing():
    raw_response = (
        '{"permissions": [], "role": "USER", "authenticated": true, '
        '"anonymous": false, "active": true, "locked": false}'
    )

    me = pykoplenti.MeData(json.loads(raw_response))

    assert me.is_locked is False
    assert me.is_active is True
    assert me.is_authenticated is True
    assert me.permissions == []
    assert me.is_anonymous is False
    assert me.role == "USER"


def test_version_parsing():
    raw_response = (
        '{"name": "PUCK RESTful API", "hostname": "scb", '
        '"api_version": "0.2.0", "sw_version": "01.26.09454"}'
    )

    version = pykoplenti.VersionData(json.loads(raw_response))

    assert version.api_version == "0.2.0"
    assert version.hostname == "scb"
    assert version.name == "PUCK RESTful API"
    assert version.sw_version == "01.26.09454"


def test_event_parsing():
    raw_response = (
        '{"start_time": "2023-02-24T23:54:20", "group": "Information", '
        '"description": "Abregelung der AC-Leistung auf Grund externer Signale oder '
        'erh\u00f6hter Netzfrequenz.", "is_active": false, "code": 5014, '
        '"category": "info", "end_time": "2023-02-24T23:56:22", '
        '"long_description": "Abregelung der AC-Leistung auf Grund externer '
        'Signale oder erh\u00f6hter Netzfrequenz."}'
    )

    event = pykoplenti.EventData(json.loads(raw_response))

    assert event.start_time == datetime(2023, 2, 24, 23, 54, 20)
    assert event.end_time == datetime(2023, 2, 24, 23, 56, 22)
    assert event.is_active is False
    assert event.code == 5014
    assert (
        event.long_description
        == "Abregelung der AC-Leistung auf Grund externer Signale oder erhöhter"
        " Netzfrequenz."
    )
    assert event.category == "info"
    assert (
        event.description
        == "Abregelung der AC-Leistung auf Grund externer Signale oder erhöhter"
        " Netzfrequenz."
    )
    assert event.group == "Information"


def test_module_parsing():
    raw_response = '{"type": "device", "id": "devices:local"}'

    module = pykoplenti.ModuleData(json.loads(raw_response))

    assert module.id == "devices:local"
    assert module.type == "device"


def test_process_parsing():
    raw_response = (
        '{"id": "Statistic:Yield:Day", "unit": "", "value": 40131.2797019144}'
    )

    process_data = pykoplenti.ProcessData(json.loads(raw_response))

    assert process_data.id == "Statistic:Yield:Day"
    assert process_data.unit == ""
    assert process_data.value == 40131.2797019144


def test_settings_parsing():
    raw_response = (
        '{"type": "byte", "unit": null, "max": "2", "min": "0", '
        '"default": null, "access": "readonly", "id": "Inverter:SetState"}'
    )

    settings_data = pykoplenti.SettingsData(json.loads(raw_response))

    assert settings_data.unit is None
    assert settings_data.default is None
    assert settings_data.id == "Inverter:SetState"
    assert settings_data.max == "2"
    assert settings_data.min == "0"
    assert settings_data.type == "byte"
    assert settings_data.access == "readonly"


def test_process_data_collection_indicates_length():
    raw_response = (
        '[{"id": "Statistic:Yield:Day", "unit": "", "value": 1}, '
        '{"id": "Statistic:Yield:Month", "unit": "", "value": 2}]'
    )
    pdc = pykoplenti.ProcessDataCollection(json.loads(raw_response))

    assert len(pdc) == 2


def test_process_data_collection_index_returns_processdata():
    raw_response = (
        '[{"id": "Statistic:Yield:Day", "unit": "", "value": 1}, '
        '{"id": "Statistic:Yield:Month", "unit": "", "value": 2}]'
    )
    pdc = pykoplenti.ProcessDataCollection(json.loads(raw_response))

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
    pdc = pykoplenti.ProcessDataCollection(json.loads(raw_response))

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
