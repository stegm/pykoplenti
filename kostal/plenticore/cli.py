from kostal.plenticore import PlenticoreClient
import asyncio
from aiohttp import ClientSession
import argparse
import getpass
from prompt_toolkit import PromptSession, print_formatted_text
import os
import tempfile


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

    async def run(self, passwd):
        session = PromptSession()
        print_formatted_text('') # Initialize output

        await self.prepare_client(passwd)

        while True:
            try:
                text = await session.prompt_async('(plenticore)> ')

                if text.strip().lower() == 'exit':
                    raise EOFError()
                else:
                    cmd, *args = text.strip().split()
                    cmd = cmd.lower()
                    try:
                        func = getattr(self, 'do_' + cmd)
                    except AttributeError:
                        print_formatted_text(f'Unknown command: {cmd}')
                    else:
                        await func(*args)



            except KeyboardInterrupt:
                continue
            except EOFError:
                break

    async def do_me(self, *args):
        """Returns information about the current user."""
        me = await self.client.get_me()
        print_formatted_text(me)

    async def do_login(self, *args):
        if len(args) == 0:
            passwd = getpass.getpass()
        else:
            passwd = args[0]

        await self.client.login(passwd)
        self._session_cache.write_session_id(self.client.session_id)

    async def do_modules(self, *args):
        modules = await self.client.get_modules()
        print_formatted_text(*modules, sep='\n')

    async def do_processdata(self, *args):
        if len(args) == 0:
            print_formatted_text("At least one module must be given")
            return

        for module_id in args:
            process_data = await self.client.get_process_data(module_id=module_id)
            print_formatted_text(*process_data, sep='\n')

    async def do_settings(self, *args):
        settings_data = await self.client.get_settings()
        for id, data in settings_data.items():
            print_formatted_text(f'Module: {id}')
            print_formatted_text(*data, sep='\n')



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