# Developer Notes

## Code Format

```shell script
isort pykoplenti
black --fast pykoplenti
```

## Initialize developer environment with pipenv

```shell script
pipenv sync --dev
```

## Run pytest using tox

`tox` is configured to run pytest with different versions of pydantic.

Run all environemnts:

```shell script
tox
```

Available environments:

* `py310-pydantic1` - Python 3.10 with Pydantic 1.x
* `py310-pydantic2` - Python 3.10 with Pydantic 2.x

## Running smoke tests

The test suite contains some smoke tests that connect directly to an inverter and attempt to retrieve data from it.
These tests are normally disabled but can be enabled by setting some environment variables before running `pytest`.
It is recommended to set these variables in `.env` where `pipenv` reads them before executing a command.

| Variable         | Description                                           |
| ---------------- | ----------------------------------------------------- |
| SMOKETEST_HOST   | The ip or host of the inverter.                       |
| SMOKETEST_PORT   | The port of the web API of the inverter (default: 80) |
| SMOKETEST_PASS   | The password of the web UI                            |
