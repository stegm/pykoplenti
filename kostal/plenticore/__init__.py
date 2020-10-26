from aiohttp import ClientSession, ClientResponse
from base64 import b64encode, b64decode
from yarl import URL
from hashlib import pbkdf2_hmac
from Crypto.Cipher import AES
import hmac
import hashlib
from os import urandom
from typing import Iterable, Dict
from json import dumps
import logging


logger = logging.getLogger(__name__)


class MeData:
    """Represent the data of the 'me'-request."""
    def __init__(self, raw):
        self._raw = raw

    @property
    def is_locked(self) -> bool:
        return self._raw['locked']

    @property
    def is_active(self) -> bool:
        return self._raw['active']

    @property
    def is_authenticated(self) -> bool:
        return self._raw['authenticated']

    @property
    def permissions(self) -> Iterable[str]:
        return self._raw['permissions']

    @property
    def is_anonymous(self) -> bool:
        return self._raw['anonymous']

    @property
    def role(self) -> str:
        return self._raw['role']

    def __str__(self):
        return f'Me(locked={self.is_locked}, active={self.is_active}, authenticated={self.is_authenticated}, ' \
               f'permissions={str(self.permissions)} anonymous={self.is_anonymous} role={self.role})'

    def __repr__(self):
        return dumps(self._raw)

class ModuleData:
    """Represents a single module."""
    def __init__(self, raw):
        self._raw = raw

    @property
    def id(self) -> str:
        return self._raw['id']

    @property
    def type(self) -> str:
        return self._raw['type']

    def __str__(self):
        return f'Module(id={self.id}, type={self.type})'

    def __repr__(self):
        return dumps(self._raw)

class ProcessData:
    """Represents a single process data."""
    def __init__(self, raw):
        self._raw = raw

    @property
    def id(self) -> str:
        return self._raw['id']

    @property
    def unit(self) -> str:
        return self._raw['unit']

    @property
    def value(self) -> float:
        return self._raw['value']

    def __str__(self):
        return f'ProcessData(id={self.id}, unit={self.unit}, value={self.value})'

    def __repr__(self):
        return dumps(self._raw)

class SettingsData:
    """Represents a single settings data."""
    def __init__(self, raw):
        self._raw = raw

    @property
    def unit(self) -> str:
        return self._raw['unit']

    @property
    def default(self) -> str:
        return self._raw['default']

    @property
    def id(self) -> str:
        return self._raw['id']

    @property
    def max(self) -> str:
        return self._raw['max']

    @property
    def min(self) -> str:
        return self._raw['min']

    @property
    def type(self) -> str:
        return self._raw['type']

    @property
    def access(self) -> str:
        return self._raw['access']

    def __str__(self):
        return f'SettingsData(id={self.id}, unit={self.unit}, default={self.default}, min={self.min}, max={self.max},' \
               f'type={self.type}, access={self.access})'

    def __repr__(self):
        return dumps(self._raw)

class PlenticoreClient:
    """Client for REST-API of plenticore inverters."""

    BASE_URL = '/api/v1/'

    def __init__(self, websession: ClientSession, host: str, port: int = 80):
        self.websession = websession
        self.host = host
        self.port = port
        self.session_id = None

    def _create_url(self, path: str) -> URL:
        """Creates a REST-API URL with the given path as suffix."""
        base = URL.build(scheme='http', host=self.host, port=self.port, path=PlenticoreClient.BASE_URL)
        return base.join(URL(path))

    async def login(self, password: str, user: str = 'user'):
        # Step 1 start authentication
        client_nonce = urandom(12)

        start_request = {
            "username": user,
            "nonce": b64encode(client_nonce).decode('utf-8')
        }

        async with self.websession.request(
            "POST", self._create_url('auth/start'), json=start_request
        ) as resp:
            start_response = await resp.json()
            server_nonce = b64decode(start_response['nonce'])
            transaction_id = b64decode(start_response['transactionId'])
            salt = b64decode(start_response['salt'])
            rounds = start_response['rounds']

        # Step 2 finish authentication (RFC5802)
        salted_passwd = pbkdf2_hmac('sha256', password.encode('utf-8'), salt, rounds)
        client_key = hmac.new(salted_passwd, 'Client Key'.encode('utf-8'), hashlib.sha256).digest()
        stored_key = hashlib.sha256(client_key).digest()

        auth_msg = 'n={user},r={client_nonce},r={server_nonce},s={salt},i={rounds},c=biws,r={server_nonce}'.format(
            user=user,
            client_nonce=b64encode(client_nonce).decode('utf-8'),
            server_nonce=b64encode(server_nonce).decode('utf-8'),
            salt=b64encode(salt).decode('utf-8'),
            rounds=rounds
        )
        client_signature = hmac.new(stored_key, auth_msg.encode('utf-8'), hashlib.sha256).digest()
        client_proof = bytes([a ^ b for a, b in zip(client_key, client_signature)])

        server_key = hmac.new(salted_passwd, 'Server Key'.encode('utf-8'), hashlib.sha256).digest()
        server_signature = hmac.new(server_key, auth_msg.encode('utf-8'), hashlib.sha256).digest()

        finish_request = {
            "transactionId": b64encode(transaction_id).decode('utf-8'),
            "proof": b64encode(client_proof).decode('utf-8')
        }

        async with self.websession.request(
            "POST", self._create_url('auth/finish'), json=finish_request
        ) as resp:
            finish_response = await resp.json()
            token = finish_response['token']
            signature = b64decode(finish_response['signature'])
            if signature != server_signature:
                raise Exception('Server signature mismatch.')

        # Step 3 create session
        session_key_hmac = hmac.new(stored_key, 'Session Key'.encode('utf-8'), hashlib.sha256)
        session_key_hmac.update(auth_msg.encode('utf-8'))
        session_key_hmac.update(client_key)
        protocol_key = session_key_hmac.digest()
        session_nonce = urandom(16)
        cipher = AES.new(protocol_key, AES.MODE_GCM, nonce=session_nonce)
        cipher_text, auth_tag = cipher.encrypt_and_digest(token.encode('utf-8'))

        session_request = {
            'transactionId': b64encode(transaction_id).decode('utf-8'),
            'iv': b64encode(session_nonce).decode('utf-8'),
            'tag': b64encode(auth_tag).decode('utf-8'),
            'payload': b64encode(cipher_text).decode('utf-8'),
        }

        async with self.websession.request(
            "POST", self._create_url('auth/create_session'), json=session_request
        ) as resp:
            session_response = await resp.json()
            self.session_id = session_response['sessionId']

    def _session_request(self, path: str, method='GET', **kwargs):
        """Make an request on the current active session."""
        # TODO exception if session does not exist
        headers = { 'authorization': f'Session {self.session_id}'}
        return self.websession.request(method, self._create_url(path), headers=headers, **kwargs)

    async def get_me(self) -> MeData:
        """Returns information about the user."""
        async with self._session_request('auth/me') as resp:
            me_response = await resp.json()
            return MeData(me_response)

    async def get_modules(self) -> Iterable[ModuleData]:
        """Returns list of all available modules (providing process data or settings)."""
        async with self._session_request('modules') as resp:
            modules_response = await resp.json()
            return list([ModuleData(x) for x in modules_response])

    async def get_process_data(self, module_id: str) -> Iterable[ProcessData]:
        """Returns list of all available process-data identifiers of a module."""
        async with self._session_request(f'processdata/{module_id}') as resp:
            data_response = await resp.json()
            return list([ProcessData(x) for x in data_response[0]['processdata']])

    async def get_settings(self) -> Dict[str, SettingsData]:
        """Returns list of all modules with a list of available settings identifiers."""
        async with self._session_request('settings') as resp:
            response = await resp.json()
            result = {}
            for module in response:
                id = module['moduleid']
                data = list([SettingsData(x) for x in module['settings']])
                result[id] = data

            return result
