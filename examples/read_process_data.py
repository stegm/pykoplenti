import asyncio
from aiohttp import ClientSession
from kostal.plenticore import PlenticoreApiClient
import sys

"""
Provides a simple example which reads two process data from the plenticore.

Must be called with host and password:
  `python read_process_data.py 192.168.1.100 mysecretpassword`

"""

async def async_main(host, passwd):
    async with ClientSession() as session:
        client = PlenticoreApiClient(session, host)
        await client.login(passwd)

        data = await client.get_process_data_values('devices:local', ['Inverter:State', 'Home_P'])

        device_local = data['devices:local']
        inverter_state = next(x for x in device_local if x.id == 'Inverter:State')
        home_p = next(x for x in device_local if x.id == 'Home_P')

        print(f'Inverter-State: {inverter_state.value}\nHome-P: {home_p.value}\n')


if len(sys.argv) != 3:
    print("Usage: <host> <password>")
    sys.exit(1)

_, host, passwd = sys.argv

asyncio.run(async_main(host, passwd))
