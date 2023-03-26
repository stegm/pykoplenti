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
