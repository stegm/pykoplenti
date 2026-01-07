# Python Library for Accessing Kostal Plenticore Inverters

This repository provides a python library and command line interface for the REST-API of Kostal Plenticore Solar Inverter.

This library is not affiliated with Kostal and is no offical product. It uses the interfaces of the inverter like other libs (eg. https://github.com/kilianknoll/kostal-RESTAPI) and uses information from their swagger documentation (ip-addr/api/v1/).

![CI](https://github.com/stegm/pykoplenti/workflows/CI/badge.svg)

## Features

- Authenticate
- Read/Write settings
- Read process data
- Read events
- Download of log data
- Full async-Support for reading and writing data
- [Commandline interface](doc/command_line.md) for shell access
- Dynamic data model - adapts automatically to new process data or settings
- [Virtual Process Data](doc/virtual_process_data.md) values

## Getting Started

### Prerequisites

You will need Python >=3.9.

### Installing the library

Packages of this library are released on [PyPI](https://pypi.org/project/kostal-plenticore/) and can be
installed with `pip`. Alternatively the packages can also be downloaded from
[GitHub](https://github.com/stegm/pykoplenti/releases/).

I recommend to use a [virtual environment](https://docs.python.org/3/library/venv.html) for this,
because it installs the dependecies independently from the system. The installed CLI tools can then be called
without activating the virtual environment it.

```shell
# Install with command line support
$ pip install pykoplenti[cli]

# Install without command line support (library only)
$ pip install pykoplenti
```

### Using the command line interface

After installing with CLI support, you can use the command:

```shell
$ pykoplenti --help
Usage: python -m pykoplenti.cli [OPTIONS] COMMAND [ARGS]...

  Handling of global arguments with click

Options:
  --host TEXT           Hostname or IP of the inverter
  --port INTEGER        Port of the inverter  [default: 80]
  --password TEXT       Password or master key (also device id)
  --service-code TEXT   service code for installer access
  --password-file FILE  Path to password file - deprecated, use --credentials
                        [default: secrets]
  --credentials FILE    Path to the credentials file. This has a simple ini-
                        format without sections. For user access, use the
                        'password'. For installer access, use the 'master-key'
                        and 'service-key'.
  --help                Show this message and exit.

Commands:
  all-processdata   Returns a list of all available process data.
  all-settings      Returns the ids of all settings.
  download-log      Download the log data from the inverter to a file.
  read-events       Returns the last events
  read-processdata  Returns the values of the given process data.
  read-settings     Read the value of the given settings.
  repl              Provides a simple REPL for executing API requests to...
  write-settings    Write the values of the given settings.
```

Visit [Command Line Help](doc/command_line.md) for example usage.

### Using the library from python

The library is fully async, there for you need an async loop and an async `ClientSession`. Please refer to the
example directory for full code.

Import the client module:

```python
from pykoplenti import ApiClient
```

To communicate with the inverter you need to instantiate the client:

```python
# session is a aiohttp ClientSession
client = ApiClient(session, '192.168.1.100')
```

Login to gain full access to process data and settings:

```python
await client.login(passwd)
```

Now you can access the API. For example to read process data values:

```python
data = await client.get_process_data_values('devices:local', ['Inverter:State', 'Home_P'])

device_local = data['devices:local']
inverter_state = device_local['Inverter:State']
home_p = device_local['Home_P']
```

See the full example here: [read_process_data.py](examples/read_process_data.py).

If you should need installer access use the master key (printed on a label at the side of the inverter)
and additionally pass your service code:

```python
await client.login(my_master_key, service_code=my_service_code)
```

## Documentation

- [Command Line Interface](doc/command_line.md)
- [Examples](examples/)
- [Virtual Process Data](doc/virtual_process_data.md)
- [Notes about Process Data](doc/process_data.md)

## Built With

- [AIOHTTPO](https://docs.aiohttp.org/en/stable/) - asyncio for HTTP
- [click](https://click.palletsprojects.com/) - command line interface framework
- [black](https://github.com/psf/black) - Python code formatter
- [ruff](https://github.com/astral-sh/ruff) - Python linter
- [pydantic](https://docs.pydantic.dev/latest/) - Data validation library
- [pytest](https://docs.pytest.org/) - Python test framework
- [mypy](https://mypy-lang.org/) - Python type checker
- [hatchling](https://hatch.pypa.io/) - Modern Python build backend
- [tox](https://tox.wiki) - Automate testing

## License

apache-2.0

## Acknowledgments

- [kilianknoll](https://github.com/kilianknoll) for the kostal-RESTAPI project
