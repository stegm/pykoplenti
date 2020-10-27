from kostal.plenticore import PlenticoreClient
import asyncio
from aiohttp import ClientSession
import argparse
from prompt_toolkit import PromptSession, print_formatted_text
import os
import tempfile
from ast import literal_eval
from inspect import iscoroutinefunction
import traceback

class SessionCache:
    """Persistent the session in a temporary file."""
    def __init__(self, host):
        self.host = host

    def read_session_id(self) -> str:
        file = os.path.join(tempfile.gettempdir(), f'plenticore-session-{self.host}')
        if os.path.isfile(file):
            with open(file, 'rt') as f:
                return f.readline(256)
        else:
            return None

    def write_session_id(self, id: str):
        file = os.path.join(tempfile.gettempdir(), f'plenticore-session-{self.host}')
        f = os.open(file, os.O_WRONLY | os.O_TRUNC | os.O_CREAT, mode=0o600)
        try:
            os.write(f, id.encode('ascii'))
        finally:
            os.close(f)



class PlenticoreShell:
    """Provides a shell-like access to the plenticore client."""
    def __init__(self, client: PlenticoreClient):
        super().__init__()
        self.client = client
        self._session_cache = SessionCache(self.client.host)

    async def prepare_client(self, passwd):
        # first try to reuse existing session
        session_id = self._session_cache.read_session_id()
        if session_id is not None:
            self.client.session_id = session_id
            print_formatted_text('Trying to reuse existing session... ', end=None)
            me = await self.client.get_me()
            if me.is_authenticated:
                print_formatted_text('Success')
                return
            else:
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
        print_formatted_text(flush=True) # Initialize output

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
                elif text.strip() == '':
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

                    self.print_result(result)

            except KeyboardInterrupt:
                continue
            except EOFError:
                break

    def print_result(self, result):
        """Print the result of the method call."""
        if isinstance(result, dict):
            for k, v in result.items():
                if hasattr(v, '__iter__') and not isinstance(v, str):
                    print_formatted_text(f'{k}:')
                    print_formatted_text(*v, sep='\n')
                else:
                    print_formatted_text(f'{k}: {v}')
        elif hasattr(result, '__iter__') and not isinstance(result, str):
            print_formatted_text(*result, sep='\n')
        else:
            print_formatted_text(result)



async def main(host, port, passwd):
    async with ClientSession() as session:
        client = PlenticoreClient(session, host=host, port=port)

        shell = PlenticoreShell(client)
        await shell.run(passwd)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Plenticore command line client.')
    parser.add_argument('--host', type=str, required=True,
                        help='hostname or ip of plenticore inverter')
    parser.add_argument('--port', type=int, default=80,
                        help='port of plenticore (default 80)')
    parser.add_argument('--password', type=str, default=None,
                        help='password')
    parser.add_argument('--password-file', type=str, default='secrets',
                        help='password file (default "secrets" in the current working directory)')

    args = parser.parse_args()

    if args.password is not None:
        passwd = args.password
    elif os.path.isfile(args.password_file):
        with open(args.password_file, 'rt') as f:
            passwd = f.readline()
    else:
        passwd = None


    asyncio.run(main(args.host, args.port, passwd))