from base64 import b64decode, b64encode
from collections.abc import Mapping
import contextlib
from datetime import datetime
import functools
import hashlib
import hmac
import locale
import logging
from os import urandom
from typing import IO, Dict, Final, Iterable, List, Union, overload
import warnings

from Crypto.Cipher import AES
from aiohttp import ClientResponse, ClientSession, ClientTimeout
from yarl import URL

from .model import (
    EventData,
    MeData,
    ModuleData,
    ProcessDataCollection,
    SettingsData,
    VersionData,
    process_data_list,
)

_logger: Final = logging.getLogger(__name__)


class ApiException(Exception):
    """Base exception for API calls."""

    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return f"API Error: {self.msg}"


class InternalCommunicationException(ApiException):
    """Exception for internal communication error response."""

    def __init__(self, status_code: int, error: str):
        super().__init__(f"Internal communication error ([{status_code}] - {error})")
        self.status_code = status_code
        self.error = error


class AuthenticationException(ApiException):
    """Exception for authentication or user error response."""

    def __init__(self, status_code: int, error: str):
        super().__init__(
            f"Invalid user/Authentication failed ([{status_code}] - {error})"
        )
        self.status_code = status_code
        self.error = error


class NotAuthorizedException(ApiException):
    """Exception for calles without authentication."""

    def __init__(self, status_code: int, error: str):
        super().__init__(f"Not authorized ([{status_code}] - {error})")
        self.status_code = status_code
        self.error = error


class UserLockedException(ApiException):
    """Exception for user locked error response."""

    def __init__(self, status_code: int, error: str):
        super().__init__(f"User is locked ([{status_code}] - {error})")
        self.status_code = status_code
        self.error = error


class ModuleNotFoundException(ApiException):
    """Exception for module or setting not found response."""

    def __init__(self, status_code: int, error: str):
        super().__init__(f"Module or setting not found ([{status_code}] - {error})")
        self.status_code = status_code
        self.error = error


def _relogin(fn):
    """Decorator for automatic re-login if session was expired."""

    @functools.wraps(fn)
    async def _wrapper(self: "ApiClient", *args, **kwargs):
        with contextlib.suppress(AuthenticationException, NotAuthorizedException):
            return await fn(self, *args, **kwargs)
        _logger.debug("Request failed - try to re-login")
        await self._login()
        return await fn(self, *args, **kwargs)

    return _wrapper


class ApiClient(contextlib.AbstractAsyncContextManager):
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

    BASE_URL = "/api/v1/"
    SUPPORTED_LANGUAGES = {
        "de": ["de"],
        "en": ["gb"],
        "es": ["es"],
        "fr": ["fr"],
        "hu": ["hu"],
        "it": ["it"],
        "nl": ["nl"],
        "pl": ["pl"],
        "pt": ["pt"],
        "cs": ["cz"],
        "el": ["gr"],
        "zh": ["cn"],
    }

    def __init__(self, websession: ClientSession, host: str, port: int = 80):
        """Create a new client.

        :param websession: A aiohttp ClientSession for all requests
        :param host: The hostname or ip of the inverter
        :param port: The port of the API interface (default 80)
        """
        self.websession = websession
        self.host = host
        self.port = port
        self.session_id: Union[str, None] = None
        self._key: Union[str, None] = None
        self._service_code: Union[str, None] = None
        self._user: Union[str, None] = None

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Logout support for context manager."""
        if self.session_id is not None:
            await self.logout()

    def _create_url(self, path: str) -> URL:
        """Creates a REST-API URL with the given path as suffix.

        :param path: path suffix, must not start with '/'
        :return: a URL instance
        """
        base = URL.build(
            scheme="http",
            host=self.host,
            port=self.port,
            path=ApiClient.BASE_URL,
        )
        return base.join(URL(path))

    async def initialize_virtual_process_data(self):
        process_data = await self.get_process_data()
        self._virt_process_data.initialize(process_data)

    async def login(
        self,
        key: str,
        service_code: Union[str, None] = None,
        password: Union[str, None] = None,
        user: Union[str, None] = None,
    ):
        """Login with the given password (key).

        If a service code is provided user is 'master', else 'user'.

        Parameters
        ----------
        :param key: The user password. If 'service_code' is given, 'key' is the
                    Master Key (also called Device ID).
        :type key: str, None
        :param service_code: Installer service code. If given the user is assumed to be
                             'master', else 'user'.
        :type service_code: str, None
        :param password: Deprecated, use key instead.
        :param user: Deprecated, user is chosen automatically depending on service_code.

        :raises AuthenticationException: if authentication failed
        :raises aiohttp.client_exceptions.ClientConnectorError: if host is not reachable
        :raises asyncio.exceptions.TimeoutError: if a timeout occurs
        """

        if password is None:
            self._key = key
        else:
            warnings.warn(
                "password is deprecated. Use key instead.", DeprecationWarning
            )
            self._key = password

        if user is None:
            self._user = "master" if service_code else "user"
        else:
            warnings.warn(
                "user is deprecated. user is chosen automatically.", DeprecationWarning
            )

        self._service_code = service_code

        try:
            await self._login()
        except Exception:
            self._key = None
            self._user = None
            self._service_code = None
            raise

    async def _login(self):
        # Step 1 start authentication
        client_nonce = urandom(12)

        start_request = {
            "username": self._user,
            "nonce": b64encode(client_nonce).decode("utf-8"),
        }

        async with self.websession.request(
            "POST", self._create_url("auth/start"), json=start_request
        ) as resp:
            await self._check_response(resp)
            start_response = await resp.json()
            server_nonce = b64decode(start_response["nonce"])
            transaction_id = b64decode(start_response["transactionId"])
            salt = b64decode(start_response["salt"])
            rounds = start_response["rounds"]

        # Step 2 finish authentication (RFC5802)
        salted_passwd = hashlib.pbkdf2_hmac(
            "sha256", self._key.encode("utf-8"), salt, rounds
        )
        client_key = hmac.new(
            salted_passwd, "Client Key".encode("utf-8"), hashlib.sha256
        ).digest()
        stored_key = hashlib.sha256(client_key).digest()

        auth_msg = (
            "n={user},r={client_nonce},r={server_nonce},s={salt},i={rounds},"
            "c=biws,r={server_nonce}".format(
                user=self._user,
                client_nonce=b64encode(client_nonce).decode("utf-8"),
                server_nonce=b64encode(server_nonce).decode("utf-8"),
                salt=b64encode(salt).decode("utf-8"),
                rounds=rounds,
            )
        )
        client_signature = hmac.new(
            stored_key, auth_msg.encode("utf-8"), hashlib.sha256
        ).digest()
        client_proof = bytes(a ^ b for a, b in zip(client_key, client_signature))

        server_key = hmac.new(
            salted_passwd, "Server Key".encode("utf-8"), hashlib.sha256
        ).digest()
        server_signature = hmac.new(
            server_key, auth_msg.encode("utf-8"), hashlib.sha256
        ).digest()

        finish_request = {
            "transactionId": b64encode(transaction_id).decode("utf-8"),
            "proof": b64encode(client_proof).decode("utf-8"),
        }

        async with self.websession.request(
            "POST", self._create_url("auth/finish"), json=finish_request
        ) as resp:
            await self._check_response(resp)
            finish_response = await resp.json()
            token = finish_response["token"]
            signature = b64decode(finish_response["signature"])
            if signature != server_signature:
                raise Exception("Server signature mismatch.")

        # Step 3 create session
        session_key_hmac = hmac.new(
            stored_key, "Session Key".encode("utf-8"), hashlib.sha256
        )
        session_key_hmac.update(auth_msg.encode("utf-8"))
        session_key_hmac.update(client_key)
        protocol_key = session_key_hmac.digest()
        session_nonce = urandom(16)
        cipher = AES.new(protocol_key, AES.MODE_GCM, nonce=session_nonce)

        if self._user == "master":
            token = f"{token}:{self._service_code}"

        cipher_text, auth_tag = cipher.encrypt_and_digest(token.encode("utf-8"))

        session_request = {
            # AES initialization vector
            "iv": b64encode(session_nonce).decode("utf-8"),
            # AES GCM tag
            "tag": b64encode(auth_tag).decode("utf-8"),
            # ID of authentication transaction
            "transactionId": b64encode(transaction_id).decode("utf-8"),
            # Only the token or token and service code (separated by colon). Encrypted
            # with AES using the protocol key
            "payload": b64encode(cipher_text).decode("utf-8"),
        }

        async with self.websession.request(
            "POST", self._create_url("auth/create_session"), json=session_request
        ) as resp:
            await self._check_response(resp)
            session_response = await resp.json()
            self.session_id = session_response["sessionId"]

    def _session_request(self, path: str, method="GET", **kwargs):
        """Make an request on the current active session.

        :param path: the URL suffix
        :param method: the request method, defaults to 'GET'
        :param **kwargs: all other args are forwarded to the request
        """

        headers: Dict[str, str] = {}
        if self.session_id is not None:
            headers["authorization"] = f"Session {self.session_id}"

        return self.websession.request(
            method, self._create_url(path), headers=headers, **kwargs
        )

    async def _check_response(self, resp: ClientResponse):
        """Check if the given response contains an error and throws
        the appropriate exception."""

        if resp.status == 200:
            return

        try:
            response = await resp.json()
            error = response["message"]
        except Exception:
            error = None

        if resp.status == 400:
            raise AuthenticationException(resp.status, error)

        if resp.status == 401:
            raise NotAuthorizedException(resp.status, error)

        if resp.status == 403:
            raise UserLockedException(resp.status, error)

        if resp.status == 404:
            raise ModuleNotFoundException(resp.status, error)

        if resp.status == 503:
            raise InternalCommunicationException(resp.status, error)

        # we got an undocumented status code
        raise ApiException(f"Unknown API response [{resp.status}] - {error}")

    async def logout(self):
        """Logs the current user out."""
        self._key = None
        self._service_code = None
        async with self._session_request("auth/logout", method="POST") as resp:
            await self._check_response(resp)

    async def get_me(self) -> MeData:
        """Returns information about the user.

        No login is required.
        """
        async with self._session_request("auth/me") as resp:
            await self._check_response(resp)
            me_response = await resp.json()
            return MeData(**me_response)

    async def get_version(self) -> VersionData:
        """Returns information about the API of the inverter.

        No login is required.
        """
        async with self._session_request("info/version") as resp:
            await self._check_response(resp)
            response = await resp.json()
            return VersionData(**response)

    @_relogin
    async def get_events(self, max_count=10, lang=None) -> Iterable[EventData]:
        """Returns a list with the latest localized events.

        :param max_count: the max number of events to read
        :param lang: the RFC1766 based language code, for example 'de_CH' or 'en'
        """
        if lang is None:
            lang = locale.getlocale()[0]

        language = lang[:2].lower()
        variant = lang[3:5].lower()
        if language not in ApiClient.SUPPORTED_LANGUAGES.keys():
            # Fallback to default
            language = "en"
            variant = "gb"
        else:
            variants = ApiClient.SUPPORTED_LANGUAGES[language]
            if variant not in variants:
                variant = variants[0]

        request = {"language": f"{language}-{variant}", "max": max_count}

        async with self._session_request(
            "events/latest", method="POST", json=request
        ) as resp:
            await self._check_response(resp)
            event_response = await resp.json()
            return [EventData(**x) for x in event_response]

    async def get_modules(self) -> Iterable[ModuleData]:
        """Return list of all available modules (providing process data or settings)."""
        async with self._session_request("modules") as resp:
            await self._check_response(resp)
            modules_response = await resp.json()
            return [ModuleData(**x) for x in modules_response]

    @_relogin
    async def get_process_data(self) -> Mapping[str, Iterable[str]]:
        """Return a dictionary of all processdata ids and its module ids.

        :return: a dictionary with the module id as key and a list of process data ids
                 as value
        """
        async with self._session_request("processdata") as resp:
            await self._check_response(resp)
            data_response = await resp.json()
            return {x["moduleid"]: x["processdataids"] for x in data_response}

    @overload
    async def get_process_data_values(
        self,
        module_id: str,
        processdata_id: str,
    ) -> Mapping[str, ProcessDataCollection]: ...

    @overload
    async def get_process_data_values(
        self,
        module_id: str,
        processdata_id: Iterable[str],
    ) -> Mapping[str, ProcessDataCollection]: ...

    @overload
    async def get_process_data_values(
        self,
        module_id: str,
    ) -> Mapping[str, ProcessDataCollection]: ...

    @overload
    async def get_process_data_values(
        self,
        module_id: Mapping[str, Iterable[str]],
    ) -> Mapping[str, ProcessDataCollection]: ...

    @overload
    async def get_process_data_values(
        self,
        module_id: Union[str, Mapping[str, Iterable[str]]],
        processdata_id: Union[str, Iterable[str], None] = None,
    ) -> Mapping[str, ProcessDataCollection]: ...

    @_relogin
    async def get_process_data_values(
        self,
        module_id: Union[str, Mapping[str, Iterable[str]]],
        processdata_id: Union[str, Iterable[str], None] = None,
    ) -> Mapping[str, ProcessDataCollection]:
        """Return a dictionary of process data of one or more modules.

        :param module_id: required, must be a module id or a mapping with the
                          module id as key and the process data ids as values.
        :param processdata_id: optional, if given `module_id` must be string. Can
                               be either a string or a list of string. If missing
                               all process data ids are returned.
        :return: a dictionary with the module id as key and a instance of
                 :py:class:`ProcessDataCollection` as value
        """

        if isinstance(module_id, str) and processdata_id is None:
            # get all process data of a module
            async with self._session_request(f"processdata/{module_id}") as resp:
                await self._check_response(resp)
                data_response = await resp.json()
                return {
                    data_response[0]["moduleid"]: ProcessDataCollection(
                        process_data_list(data_response[0]["processdata"])
                    )
                }

        if isinstance(module_id, str) and isinstance(processdata_id, str):
            # get a single process data of a module
            async with self._session_request(
                f"processdata/{module_id}/{processdata_id}"
            ) as resp:
                await self._check_response(resp)
                data_response = await resp.json()
                return {
                    data_response[0]["moduleid"]: ProcessDataCollection(
                        process_data_list(data_response[0]["processdata"])
                    )
                }

        if (
            isinstance(module_id, str)
            and processdata_id is not None
            and hasattr(processdata_id, "__iter__")
        ):
            # get multiple process data of a module
            ids = ",".join(processdata_id)
            async with self._session_request(f"processdata/{module_id}/{ids}") as resp:
                await self._check_response(resp)
                data_response = await resp.json()
                return {
                    data_response[0]["moduleid"]: ProcessDataCollection(
                        process_data_list(data_response[0]["processdata"])
                    )
                }

        if isinstance(module_id, dict) and processdata_id is None:
            # get multiple process data of multiple modules
            request = []
            for mid, pids in module_id.items():
                # the json encoder expects that iterables are either list or tuples,
                # other types has to be converted
                if isinstance(pids, (list, tuple)):
                    request.append(dict(moduleid=mid, processdataids=pids))
                else:
                    request.append(dict(moduleid=mid, processdataids=list(pids)))

            async with self._session_request(
                "processdata", method="POST", json=request
            ) as resp:
                await self._check_response(resp)
                data_response = await resp.json()
                return {
                    x["moduleid"]: ProcessDataCollection(
                        process_data_list(x["processdata"])
                    )
                    for x in data_response
                }

        raise TypeError("Invalid combination of module_id and processdata_id.")

    async def get_settings(self) -> Mapping[str, Iterable[SettingsData]]:
        """Return list of all modules with a list of available settings identifiers."""
        async with self._session_request("settings") as resp:
            await self._check_response(resp)
            response = await resp.json()
            result: Dict[str, List[SettingsData]] = {}
            for module in response:
                mid = module["moduleid"]
                data = [SettingsData(**x) for x in module["settings"]]
                result[mid] = data

            return result

    @overload
    async def get_setting_values(
        self,
        module_id: str,
        setting_id: str,
    ) -> Mapping[str, Mapping[str, str]]: ...

    @overload
    async def get_setting_values(
        self,
        module_id: str,
        setting_id: Iterable[str],
    ) -> Mapping[str, Mapping[str, str]]: ...

    @overload
    async def get_setting_values(
        self,
        module_id: str,
    ) -> Mapping[str, Mapping[str, str]]: ...

    @overload
    async def get_setting_values(
        self,
        module_id: Mapping[str, Iterable[str]],
    ) -> Mapping[str, Mapping[str, str]]: ...

    @_relogin
    async def get_setting_values(
        self,
        module_id: Union[str, Mapping[str, Iterable[str]]],
        setting_id: Union[str, Iterable[str], None] = None,
    ) -> Mapping[str, Mapping[str, str]]:
        """Return a dictionary of setting values of one or more modules.

        :param module_id: required, must be a module id or a dictionary with the
                          module id as key and the setting ids as values.
        :param setting_id: optional, if given `module_id` must be string. Can
                           be either a string or a list of string. If missing
                           all setting ids are returned.
        """
        if isinstance(module_id, str) and setting_id is None:
            # get all setting data of a module
            async with self._session_request(f"settings/{module_id}") as resp:
                await self._check_response(resp)
                data_response = await resp.json()
                return {module_id: {data_response[0]["id"]: data_response[0]["value"]}}

        if isinstance(module_id, str) and isinstance(setting_id, str):
            # get a single setting of a module
            async with self._session_request(
                f"settings/{module_id}/{setting_id}"
            ) as resp:
                await self._check_response(resp)
                data_response = await resp.json()
                return {module_id: {data_response[0]["id"]: data_response[0]["value"]}}

        if (
            isinstance(module_id, str)
            and setting_id is not None
            and hasattr(setting_id, "__iter__")
        ):
            # get multiple settings of a module

            # There was once an API version which explicitly supports a single module with
            # multiple settings in one request. However this way seems to be not supported anymore
            # and hence we use the same approach as for multiple modules.
            # Known to work: Plenticore plus 10
            # Known not to work: Plenticore plus 10 G2, Plenticore M G3
            request = [
                {
                    "moduleid": module_id,
                    "settingids": list(setting_id),
                }
            ]

            async with self._session_request("settings", method="POST", json=request) as resp:
                await self._check_response(resp)
                data_response = await resp.json()
                # expected response looks like
                # [
                #   {
                #       "moduleid": <id>,
                #       "settings":
                #       [
                #           {
                #               "id": <id>,
                #               "value": <value>
                #           },
                #        ...
                #       ]
                #   },
                #  ...
                # ]
                return {
                    x["moduleid"]: {y["id"]: y["value"] for y in x["settings"]}
                    for x in data_response
                }

        if isinstance(module_id, dict) and setting_id is None:
            # get multiple process data of multiple modules
            request = []
            for mid, pids in module_id.items():
                # the json encoder expects that iterables are either list or tuples,
                # other types has to be converted
                if isinstance(pids, (list, tuple)):
                    request.append(dict(moduleid=mid, settingids=pids))
                else:
                    request.append(dict(moduleid=mid, settingids=list(pids)))

            async with self._session_request(
                "settings", method="POST", json=request
            ) as resp:
                await self._check_response(resp)
                data_response = await resp.json()
                return {
                    x["moduleid"]: {y["id"]: y["value"] for y in x["settings"]}
                    for x in data_response
                }

        raise TypeError("Invalid combination of module_id and setting_id.")

    @_relogin
    async def set_setting_values(self, module_id: str, values: Mapping[str, str]):
        """Write a list of settings for one modules."""
        request = [
            {
                "moduleid": module_id,
                "settings": [dict(value=v, id=k) for k, v in values.items()],
            }
        ]
        async with self._session_request(
            "settings", method="PUT", json=request
        ) as resp:
            await self._check_response(resp)

    @_relogin
    async def download_logdata(
        self,
        writer: IO,
        begin: Union[datetime, None] = None,
        end: Union[datetime, None] = None,
    ):
        """Download logdata as tab-separated file."""
        request = {}
        if begin is not None:
            request["begin"] = begin.strftime("%Y-%m-%d")
        if end is not None:
            request["end"] = end.strftime("%Y-%m-%d")

        async with self._session_request(
            "logdata/download",
            method="POST",
            json=request,
            timeout=ClientTimeout(total=360),
        ) as resp:
            await self._check_response(resp)
            async for data in resp.content.iter_any():
                writer.write(data.decode("UTF-8"))
