import contextlib
import functools
import hashlib
import hmac
import logging
from base64 import b64decode, b64encode
from collections.abc import Mapping
from json import dumps
from os import urandom
from typing import Dict, Iterable, Union

from aiohttp import ClientResponse, ClientSession
from Crypto.Cipher import AES
from yarl import URL

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
        return f'Me(locked={self.is_locked}, active={self.is_active}, ' \
               f'authenticated={self.is_authenticated}, ' \
               f'permissions={str(self.permissions)} anonymous={self.is_anonymous} ' \
               f'role={self.role})'

    def __repr__(self):
        return dumps(self._raw)

class VersionData:
    """Represent the data of the 'version'-request."""
    def __init__(self, raw):
        self._raw = raw

    @property
    def api_version(self) -> str:
        return self._raw['api_version']

    @property
    def hostname(self) -> bool:
        return self._raw['hostname']

    @property
    def name(self) -> bool:
        return self._raw['name']

    @property
    def sw_version(self) -> Iterable[str]:
        return self._raw['sw_version']

    def __str__(self):
        return f'Version(api_version={self.api_version}, hostname={self.hostname}, ' \
               f'name={self.name}, sw_version={str(self.sw_version)})'

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


class ProcessDataCollection(Mapping):
    """Represents a collection of process data value."""
    def __init__(self, raw):
        self._process_data = list([ProcessData(x) for x in raw])

    def __len__(self):
        return len(self._process_data)

    def __iter__(self):
        return iter(self._process_data)

    def __getitem__(self, item):
        try:
            return next(x for x in self._process_data if x.id == item)
        except StopIteration:
            raise KeyError(item)

    def __repr__(self):
        return self._raw

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
        return f'SettingsData(id={self.id}, unit={self.unit}, default={self.default}, ' \
               f'min={self.min}, max={self.max},' \
               f'type={self.type}, access={self.access})'

    def __repr__(self):
        return dumps(self._raw)


class PlenticoreApiException(Exception):
    """Base exception for Plenticore API calls."""
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return f'Plenticore API Error: {self.msg}'

class PlenticoreInternalCommunicationException(PlenticoreApiException):
    """Exception for internal communication error response."""
    def __init__(self, status_code: int, error: str):
        super().__init__(f'Internal communication error ([{status_code}] - {error})')
        self.status_code = status_code
        self.error = error

class PlenticoreAuthenticationException(PlenticoreApiException):
    """Exception for authentiation or user error response."""
    def __init__(self, status_code: int, error: str):
        super().__init__(f'Invalid user/Authentication failed ([{status_code}] - {error})')
        self.status_code = status_code
        self.error = error

class PlenticoreUserLockedException(PlenticoreApiException):
    """Exception for user locked error response."""
    def __init__(self, status_code: int, error: str):
        super().__init__(f'User is locked ([{status_code}] - {error})')
        self.status_code = status_code
        self.error = error

class PlenticoreModuleNotFoundException(PlenticoreApiException):
    """Exception for module or setting not found response."""
    def __init__(self, status_code: int, error: str):
        super().__init__(f'Module or setting not found ([{status_code}] - {error})')
        self.status_code = status_code
        self.error = error


class PlenticoreApiClient(contextlib.AbstractAsyncContextManager):
    """Client for the REST-API of Kostal Plenticore inverters.
    
    The RESP-API provides several scopes of information. Each scope provides a
    dynamic set of data which can be retrieved using this interface. The scopes
    are:

    - process data (readonly, dynamic values of the operation)
    - settings (some are writable, static values for configuration)

    The data are grouped into modules. For example the module `devices:local`
    provides a process data `Dc_P` which contains the value of the current
    DC power.

    To get all process data or settings the methods `get_process_data` or
    `get_settings` can be used. Depending of the current logged in user the
    returned data can vary.

    The methods `get_process_data_values` and `get_setting_values` can be used 
    to read process data or setting values from the inverter. You can use 
    `set_setting_values` to write new setting values to the inverter if the
    setting is writable.

    The authorization system of the inverter comprises three states:
    * not logged in (is_active=False, authenticated=False)
    * logged in and active (is_active=True, authenticated=True)
    * logged in and inactive (is_active=False, authenticated=False)

    The current state can be queried with the `get_me` method. Depending of
    this state some operation might not be available.
    """

    BASE_URL = '/api/v1/'

    def __init__(self, websession: ClientSession, host: str, port: int = 80):
        """Create a new client.

        :param websession: A aiohttp ClientSession for all requests
        :param host: The hostname or ip of the plenticore inverter
        :param port: The port of the API interface (default 80)
        """
        self.websession = websession
        self.host = host
        self.port = port
        self.session_id = None
        self._password = None
        self._user = None

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Logout support for context manager."""
        if self.session_id is not None:
            await self.logout()

    def _create_url(self, path: str) -> URL:
        """Creates a REST-API URL with the given path as suffix.
        
        :param path: path suffix, must not start with '/'
        :return: a URL instance
        """
        base = URL.build(scheme='http',
                         host=self.host,
                         port=self.port,
                         path=PlenticoreApiClient.BASE_URL)
        return base.join(URL(path))

    async def login(self, password: str, user: str = 'user'):
        """Login the given user (default is 'user') with the given
        password.

        :raises PlenticoreAuthenticationException: if authentication failed
        :raises aiohttp.client_exceptions.ClientConnectorError: if host is not reachable
        :raises asyncio.exceptions.TimeoutError: if a timeout occurs
        """

        self._password = password
        self._user = user
        try:
            await self._login()
        except:
            self._password = None
            self._user = None
            raise

    async def _login(self):
        # Step 1 start authentication
        client_nonce = urandom(12)

        start_request = {
            "username": self._user,
            "nonce": b64encode(client_nonce).decode('utf-8')
        }

        async with self.websession.request("POST",
                                           self._create_url('auth/start'),
                                           json=start_request) as resp:
            await self._check_response(resp)
            start_response = await resp.json()
            server_nonce = b64decode(start_response['nonce'])
            transaction_id = b64decode(start_response['transactionId'])
            salt = b64decode(start_response['salt'])
            rounds = start_response['rounds']

        # Step 2 finish authentication (RFC5802)
        salted_passwd = hashlib.pbkdf2_hmac('sha256', self._password.encode('utf-8'),
                                            salt, rounds)
        client_key = hmac.new(salted_passwd, 'Client Key'.encode('utf-8'),
                              hashlib.sha256).digest()
        stored_key = hashlib.sha256(client_key).digest()

        auth_msg = 'n={user},r={client_nonce},r={server_nonce},s={salt},i={rounds},c=biws,r={server_nonce}'.format(
            user=self._user,
            client_nonce=b64encode(client_nonce).decode('utf-8'),
            server_nonce=b64encode(server_nonce).decode('utf-8'),
            salt=b64encode(salt).decode('utf-8'),
            rounds=rounds)
        client_signature = hmac.new(stored_key, auth_msg.encode('utf-8'),
                                    hashlib.sha256).digest()
        client_proof = bytes(
            [a ^ b for a, b in zip(client_key, client_signature)])

        server_key = hmac.new(salted_passwd, 'Server Key'.encode('utf-8'),
                              hashlib.sha256).digest()
        server_signature = hmac.new(server_key, auth_msg.encode('utf-8'),
                                    hashlib.sha256).digest()

        finish_request = {
            "transactionId": b64encode(transaction_id).decode('utf-8'),
            "proof": b64encode(client_proof).decode('utf-8')
        }

        async with self.websession.request("POST",
                                           self._create_url('auth/finish'),
                                           json=finish_request) as resp:
            await self._check_response(resp)
            finish_response = await resp.json()
            token = finish_response['token']
            signature = b64decode(finish_response['signature'])
            if signature != server_signature:
                raise Exception('Server signature mismatch.')

        # Step 3 create session
        session_key_hmac = hmac.new(stored_key, 'Session Key'.encode('utf-8'),
                                    hashlib.sha256)
        session_key_hmac.update(auth_msg.encode('utf-8'))
        session_key_hmac.update(client_key)
        protocol_key = session_key_hmac.digest()
        session_nonce = urandom(16)
        cipher = AES.new(protocol_key, AES.MODE_GCM, nonce=session_nonce)
        cipher_text, auth_tag = cipher.encrypt_and_digest(
            token.encode('utf-8'))

        session_request = {
            # AES initialization vector
            'iv': b64encode(session_nonce).decode('utf-8'),
            # AES GCM tag
            'tag': b64encode(auth_tag).decode('utf-8'),
            # ID of authentication transaction
            'transactionId': b64encode(transaction_id).decode('utf-8'),
            # Only the token or token and service code (separated by colon). Encrypted with
            # AES using the protocol key
            'payload': b64encode(cipher_text).decode('utf-8'),
        }

        async with self.websession.request(
                "POST",
                self._create_url('auth/create_session'),
                json=session_request) as resp:
            await self._check_response(resp)
            session_response = await resp.json()
            self.session_id = session_response['sessionId']

    def _session_request(self, path: str, method='GET', **kwargs):
        """Make an request on the current active session.
        
        :param path: the URL suffix
        :param method: the request method, defaults to 'GET'
        :param **kwargs: all other args are forwarded to the request
        """
        
        headers = {}
        if self.session_id is not None:
            headers['authorization'] = f'Session {self.session_id}'
        
        return self.websession.request(method,
                                       self._create_url(path),
                                       headers=headers,
                                       **kwargs)

    async def _check_response(self, resp: ClientResponse):
        """Check if the given response contains an error and throws
        the appropriate exception."""

        if resp.status != 200:
            try:
                response = await resp.json()
                error = response['message']
            except:
                error = None

            if resp.status == 400:
                raise PlenticoreAuthenticationException(resp.status, error)

            if resp.status == 403:
                raise PlenticoreUserLockedException(resp.status, error)

            if resp.status == 404:
                raise PlenticoreModuleNotFoundException(resp.status, error)

            if resp.status == 503:
                raise PlenticoreInternalCommunicationException(resp.status, error)

            # we got an undocumented status code
            raise PlenticoreApiException(f'Unknown API response [{resp.status}] - {error}')

    def _relogin(fn):
        """Decorator for automatic re-login if session was expired."""

        @functools.wraps(fn)
        async def _wrapper(self, *args, **kwargs):
            try:
                return await fn(self, *args, **kwargs)
            except PlenticoreAuthenticationException:
                pass

            logger.debug('Request failed - try to re-login')
            await self._login()
            return await fn(self, *args, **kwargs)

        return _wrapper

    async def logout(self):
        """Logs the current user out."""
        self._password = None
        async with self._session_request('auth/logout', method='POST') as resp:
            await self._check_response(resp)

    async def get_me(self) -> MeData:
        """Returns information about the user.

        No login is required.
        """
        async with self._session_request('auth/me') as resp:
            await self._check_response(resp)
            me_response = await resp.json()
            return MeData(me_response)

    async def get_version(self) -> VersionData:
        """Returns information about the API of the inverter.

        No login is required.
        """
        async with self._session_request('info/version') as resp:
            await self._check_response(resp)
            response = await resp.json()
            return VersionData(response)

    async def get_modules(self) -> Iterable[ModuleData]:
        """Returns list of all available modules (providing process data or settings)."""
        async with self._session_request('modules') as resp:
            await self._check_response(resp)
            modules_response = await resp.json()
            return [ModuleData(x) for x in modules_response]

    @_relogin
    async def get_process_data(self) -> Dict[str, Iterable[str]]:
        """Returns a dictionary of all processdata ids and its module ids.

        :return: a dictionary with the module id as key and a list of process data ids
                 as value
        """
        async with self._session_request('processdata') as resp:
            await self._check_response(resp)
            data_response = await resp.json()
            return {x['moduleid']: x['processdataids'] for x in data_response}

    @_relogin
    async def get_process_data_values(
        self,
        module_id: Union[str, Dict[str, Iterable[str]]],
        processdata_id: Union[str, Iterable[str]] = None
    ) -> Dict[str, ProcessDataCollection]:
        """Returns a dictionary of process data of one or more modules.

        :param module_id: required, must be a module id or a dictionary with the
                          module id as key and the process data ids as values.
        :param processdata_id: optional, if given `module_id` must be string. Can
                               be either a string or a list of string. If missing
                               all process data ids are returned.
        :return: a dictionary with the module id as key and a instance of :py:class:`ProcessDataCollection`
                 as value
        """
        if isinstance(module_id, str) and processdata_id is None:
            # get all process data of a module
            async with self._session_request(
                    f'processdata/{module_id}') as resp:
                await self._check_response(resp)
                data_response = await resp.json()
                return {
                    data_response[0]['moduleid']: ProcessDataCollection(data_response[0]['processdata'])
                }

        if isinstance(module_id, str) and isinstance(processdata_id, str):
            # get a single process data of a module
            async with self._session_request(
                    f'processdata/{module_id}/{processdata_id}') as resp:
                await self._check_response(resp)
                data_response = await resp.json()
                return {
                    data_response[0]['moduleid']: ProcessDataCollection(data_response[0]['processdata'])
                }

        if isinstance(module_id, str) and hasattr(processdata_id, '__iter__'):
            # get multiple process data of a module
            ids = ",".join(processdata_id)
            async with self._session_request(
                    f'processdata/{module_id}/{ids}') as resp:
                await self._check_response(resp)
                data_response = await resp.json()
                return {
                    data_response[0]['moduleid']: ProcessDataCollection(data_response[0]['processdata'])
                }

        if isinstance(module_id, dict) and processdata_id is None:
            # get multiple process data of multiple modules
            request = []
            for mid, pids in module_id.items():
                request.append(dict(moduleid=mid, processdataids=pids))

            async with self._session_request(f'processdata',
                                             method='POST',
                                             json=request) as resp:
                await self._check_response(resp)
                data_response = await resp.json()
                return {
                    x['moduleid']: ProcessDataCollection(x['processdata'])
                        for x in data_response
                }

        raise TypeError('Invalid combination of module_id and processdata_id.')

    async def get_settings(self) -> Dict[str, Iterable[SettingsData]]:
        """Returns list of all modules with a list of available settings identifiers."""
        async with self._session_request('settings') as resp:
            await self._check_response(resp)
            response = await resp.json()
            result = {}
            for module in response:
                id = module['moduleid']
                data = list([SettingsData(x) for x in module['settings']])
                result[id] = data

            return result

    @_relogin
    async def get_setting_values(
        self,
        module_id: Union[str, Dict[str, Iterable[str]]],
        setting_id: Union[str, Iterable[str]] = None
    ) -> Dict[str, Dict[str, str]]:
        """Returns a dictionary of setting values of one or more modules.

        :param module_id: required, must be a module id or a dictionary with the
                          module id as key and the setting ids as values.
        :param setting_id: optional, if given `module_id` must be string. Can
                           be either a string or a list of string. If missing
                           all setting ids are returned.
        """
        if isinstance(module_id, str) and setting_id is None:
            # get all setting data of a module
            async with self._session_request(
                    f'settings/{module_id}') as resp:
                await self._check_response(resp)
                data_response = await resp.json()
                return {
                    module_id: {data_response[0]['id']: data_response[0]['value']}
                }

        if isinstance(module_id, str) and isinstance(setting_id, str):
            # get a single setting of a module
            async with self._session_request(
                    f'settings/{module_id}/{setting_id}') as resp:
                await self._check_response(resp)
                data_response = await resp.json()
                return {
                    module_id: {data_response[0]['id']: data_response[0]['value']}
                }


        if isinstance(module_id, str) and hasattr(setting_id, '__iter__'):
            # get multiple settings of a module
            ids = ",".join(setting_id)
            async with self._session_request(
                    f'settings/{module_id}/{ids}') as resp:
                await self._check_response(resp)
                data_response = await resp.json()
                return {
                    module_id: {x['id']: x['value'] for x in data_response}
                }


        if isinstance(module_id, dict) and setting_id is None:
            # get multiple process data of multiple modules
            request = []
            for mid, pids in module_id.items():
                request.append(dict(moduleid=mid, settingids=pids))

            async with self._session_request(f'settings',
                                             method='POST',
                                             json=request) as resp:
                await self._check_response(resp)
                data_response = await resp.json()
                return {
                    x['moduleid']: {y['id']: y['value'] for y in x['settings']} for x in data_response
                }

        raise TypeError('Invalid combination of module_id and setting_id.')


    @_relogin
    async def set_setting_values(self, module_id: str, values: Dict[str, str]):
        """Writes a list of settings for one modules."""
        request = [{
            'moduleid':
            module_id,
            'settings':
            list([dict(value=v, id=k) for k, v in values.items()])
        }]
        async with self._session_request(f'settings',
                                         method='PUT',
                                         json=request) as resp:
            await self._check_response(resp)
