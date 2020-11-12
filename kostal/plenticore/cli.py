import asyncio
import os
from pprint import pprint
import re
import tempfile
import traceback
from ast import literal_eval
from collections import defaultdict
from inspect import iscoroutinefunction
from typing import Callable

import click
from aiohttp import ClientSession, ClientTimeout
from prompt_toolkit import PromptSession, print_formatted_text

from kostal.plenticore import PlenticoreApiClient


class SessionCache:
    """Persistent the session in a temporary file."""
    def __init__(self, host):
        self.host = host

    def read_session_id(self) -> str:
        file = os.path.join(tempfile.gettempdir(),
                            f'plenticore-session-{self.host}')
        if os.path.isfile(file):
            with open(file, 'rt') as f:
                return f.readline(256)
        else:
            return None

    def write_session_id(self, id: str):
        file = os.path.join(tempfile.gettempdir(),
                            f'plenticore-session-{self.host}')
        f = os.open(file, os.O_WRONLY | os.O_TRUNC | os.O_CREAT, mode=0o600)
        try:
            os.write(f, id.encode('ascii'))
        finally:
            os.close(f)


class PlenticoreShell:
    """Provides a shell-like access to the plenticore client."""
    def __init__(self, client: PlenticoreApiClient):
        super().__init__()
        self.client = client
        self._session_cache = SessionCache(self.client.host)

    async def prepare_client(self, passwd):
        # first try to reuse existing session
        session_id = self._session_cache.read_session_id()
        if session_id is not None:
            self.client.session_id = session_id
            print_formatted_text('Trying to reuse existing session... ',
                                 end=None)
            me = await self.client.get_me()
            if me.is_authenticated:
                print_formatted_text('Success')
                return

            print_formatted_text('Failed')

        if passwd is not None:
            print_formatted_text('Logging in... ', end=None)
            await self.client.login(passwd)
            self._session_cache.write_session_id(self.client.session_id)
            print_formatted_text('Success')

    def print_exception(self):
        """Prints an excpetion from executing a method."""
        print_formatted_text(traceback.format_exc())

    async def run(self, passwd):
        session = PromptSession()
        print_formatted_text(flush=True)  # Initialize output

        # Test commands:
        # get_settings
        # get_setting_values 'devices:local' 'Battery:MinSoc'
        # get_setting_values 'devices:local' ['Battery:MinSoc','Battery:MinHomeComsumption']
        # get_setting_values 'scb:time'
        # set_setting_values 'devices:local' {'Battery:MinSoc':'15'}

        await self.prepare_client(passwd)

        while True:
            try:
                text = await session.prompt_async('(plenticore)> ')

                if text.strip().lower() == 'exit':
                    raise EOFError()

                if text.strip() == '':
                    continue
                else:
                    # TODO split does not know about lists or dicts or strings with spaces
                    method_name, *arg_values = text.strip().split()

                    if method_name == 'help':
                        if len(arg_values) == 0:
                            print_formatted_text("Try: help <command>")
                        else:
                            method = getattr(self.client, arg_values[0])
                            print_formatted_text(method.__doc__)
                        continue

                    try:
                        method = getattr(self.client, method_name)
                    except AttributeError:
                        print_formatted_text(f'Unknown method: {method_name}')
                        continue

                    try:
                        args = list([literal_eval(x) for x in arg_values])
                    except:
                        print_formatted_text('Error parsing arguments')
                        self.print_exception()
                        continue

                    try:
                        if iscoroutinefunction(method):
                            result = await method(*args)
                        else:
                            result = method(*args)
                    except:
                        print_formatted_text('Error executing method')
                        self.print_exception()
                        continue

                    pprint(result)

            except KeyboardInterrupt:
                continue
            except EOFError:
                break


async def repl_main(host, port, passwd):
    async with ClientSession(timeout=ClientTimeout(total=10)) as session:
        client = PlenticoreApiClient(session, host=host, port=port)

        shell = PlenticoreShell(client)
        await shell.run(passwd)


async def command_main(host: str, port: int, passwd: str,
                       fn: Callable[[PlenticoreApiClient], None]):
    async with ClientSession(timeout=ClientTimeout(total=10)) as session:
        client = PlenticoreApiClient(session, host=host, port=port)
        session_cache = SessionCache(host)

        # Try to reuse an existing session
        client.session_id = session_cache.read_session_id()
        me = await client.get_me()
        if not me.is_authenticated:
            # create a new session
            await client.login(passwd)
            session_cache.write_session_id(client.session_id)

        await fn(client)


class GlobalArgs:
    """Global arguments over all sub commands."""
    def __init__(self):
        self.host = None
        self.port = None
        self.password = None
        self.password_file = None


pass_global_args = click.make_pass_decorator(GlobalArgs, ensure=True)


@click.group()
@click.option('--host', help='hostname or ip of plenticore inverter')
@click.option('--port', default=80, help='port of plenticore (default 80)')
@click.option('--password', default=None, help='the password')
@click.option(
    '--password-file',
    default='secrets',
    help='password file (default "secrets" in the current working directory)')
@pass_global_args
def cli(global_args, host, port, password, password_file):
    """Handling of global arguments with click"""
    if password is not None:
        global_args.passwd = password
    elif os.path.isfile(password_file):
        with open(password_file, 'rt') as f:
            global_args.passwd = f.readline()
    else:
        global_args.passwd = None

    global_args.host = host
    global_args.port = port


@cli.command()
@pass_global_args
def repl(global_args):
    """Provides a simple REPL for executing API requests to plenticore inverters."""
    asyncio.run(
        repl_main(global_args.host, global_args.port, global_args.passwd))


@cli.command()
@pass_global_args
def all_processdata(global_args):
    """Returns a list of all available process data."""
    async def fn(client: PlenticoreApiClient):
        data = await client.get_process_data()
        for k, v in data.items():
            for x in v:
                print(f'{k}/{x}')

    asyncio.run(
        command_main(global_args.host, global_args.port, global_args.passwd,
                     fn))


@cli.command()
@click.argument('ids', required=True, nargs=-1)
@pass_global_args
def read_processdata(global_args, ids):
    """Returns the values of the given process data.

    IDS is the identifier (<module_id>/<processdata_id>) of one or more processdata
    to read.

    \b
    Examples:
        read-processdata devices:local/Inverter:State
    """
    async def fn(client: PlenticoreApiClient):
        if len(ids) == 1 and '/' not in ids[0]:
            # all process data ids of a moudle
            values = await client.get_process_data_values(ids[0])
        else:
            query = defaultdict(list)
            for id in ids:
                m = re.match(r'(?P<module_id>.+)/(?P<processdata_id>.+)', id)
                if not m:
                    raise Exception(f'Invalid format of {id}')

                module_id = m.group('module_id')
                setting_id = m.group('processdata_id')

                query[module_id].append(setting_id)

            values = await client.get_process_data_values(query)

        for k, v in values.items():
            for x in v:
                print(f'{k}/{x.id}={x.value}')

    asyncio.run(
        command_main(global_args.host, global_args.port, global_args.passwd,
                     fn))


@cli.command()
@click.option('--rw', is_flag=True, default=False, help='display only writable settings')
@pass_global_args
def all_settings(global_args, rw):
    """Returns the ids of all settings."""
    async def fn(client: PlenticoreApiClient):
        settings = await client.get_settings()
        for k, v in settings.items():
            for x in v:
                if not rw or x.access == 'readwrite':
                    print(f'{k}/{x.id}')

    asyncio.run(
        command_main(global_args.host, global_args.port, global_args.passwd,
                     fn))


@cli.command()
@click.argument('ids', required=True, nargs=-1)
@pass_global_args
def read_settings(global_args, ids):
    """Read the value of the given settings.

    IDS is the identifier (<module_id>/<setting_id>) of one or more settings to read

    \b
    Examples:
        read-settings devices:local/Battery:MinSoc
        read-settings devices:local/Battery:MinSoc devices:local/Battery:MinHomeComsumption
    """
    async def fn(client: PlenticoreApiClient):
        query = defaultdict(list)
        for id in ids:
            m = re.match(r'(?P<module_id>.+)/(?P<setting_id>.+)', id)
            if not m:
                raise Exception(f'Invalid format of {id}')

            module_id = m.group('module_id')
            setting_id = m.group('setting_id')

            query[module_id].append(setting_id)

        values = await client.get_setting_values(query)

        for k, x in values.items():
            for i, v in x.items():
                print(f'{k}/{i}={v}')

    asyncio.run(
        command_main(global_args.host, global_args.port, global_args.passwd,
                     fn))


@cli.command()
@click.argument('id_values', required=True, nargs=-1)
@pass_global_args
def write_settings(global_args, id_values):
    """Write the values of the given settings.

    ID_VALUES is the identifier plus the the value to write

    \b
    Examples:
        write-settings devices:local/Battery:MinSoc=15
        """
    async def fn(client: PlenticoreApiClient):
        query = defaultdict(dict)
        for id_value in id_values:
            m = re.match(r'(?P<module_id>.+)/(?P<setting_id>.+)=(?P<value>.+)',
                         id_value)
            if not m:
                raise Exception(f'Invalid format of {id_value}')

            module_id = m.group('module_id')
            setting_id = m.group('setting_id')
            value = m.group('value')

            query[module_id][setting_id] = value

        for module_id, setting_values in query.items():
            await client.set_setting_values(module_id, setting_values)

    asyncio.run(
        command_main(global_args.host, global_args.port, global_args.passwd,
                     fn))


# entry point for pycharm; should not be used for commandline usage
if __name__ == '__main__':
    import sys
    cli(sys.argv[1:])
