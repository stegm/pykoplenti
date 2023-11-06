import asyncio
import sys

from aiohttp import ClientSession

from pykoplenti import ExtendedApiClient

"""
Provides a simple example which reads virtual process data from the plenticore.

Must be called with host and password:
  `python read_virtual_process_data.py 192.168.1.100 mysecretpassword`

"""


async def async_main(host, passwd):
    async with ClientSession() as session:
        client = ExtendedApiClient(session, host)
        await client.login(passwd)

        data = await client.get_process_data_values("_virt_", "pv_P")

        pv_power = data["_virt_"]["pv_P"]

        print(f"PV power: {pv_power}")


if len(sys.argv) != 3:
    print("Usage: <host> <password>")
    sys.exit(1)

_, host, passwd = sys.argv

asyncio.run(async_main(host, passwd))
