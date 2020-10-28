# Project Title

Provides a library and command line interface for the REST-API of Kostal Plenticore Solar Inverter.

## Features

* Authenticate
* Read/Write settings

**Planned**
* Read events
* Read process data


## Getting Started

### Prerequisites

You will need Python >=3.8.

### Installing

Checkout the code from Github:

```shell script
~$ git clone https://github.com/stegm/kostal_plenticore.git
```

Then install the library in editable mode.

```shell script
~$ cd kostal_plenticore
~/kostal_plenticore$ pip install --editable . 
```

Now you can use the command line interface to do some queries:

```shell script
~/kostal_plenticore$ plenticore --host 192.168.1.100 --password secret read-settings scb:network/Hostname
scb:network/Hostname=scb
```


## Built With

* [AIOHTTPO](https://docs.aiohttp.org/en/stable/) - asyncio for HTTP
* [click](https://click.palletsprojects.com/) - command line interface framework

## License

apache-2.0

## Acknowledgments

* [kilianknoll](https://github.com/kilianknoll) for the kostal-RESTAPI project 
