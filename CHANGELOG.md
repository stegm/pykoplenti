# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.2]

## Changed

- Loosen version for required package aiohttp (Dependency to Home Assistant).

## [1.2.1]

### Changed

- Downgrade pydantic to 1.x (Dependency to Home Assistant).

## [1.2.0]

### Changed

- All models are now based on pydantic - interface is still the same.
- Code is refactored into separate modules - imports are still provided by using `import pykoplenti`

### Fixed

- If a request is anwered with 401, an automatic re-login is triggered (like this was already the case for 400 response).

### Added

- A new api client `ExtendedApiClient` was added which provides virtual process data values. See [Virtual Process Data](doc/virtual_process_data.md) for details.
- Package provide type hints via `py.typed`.

## [1.1.0]

### Added

- Add installer authentication
- Add a new class `pykoplenti.ExtendedApiClient` which provides virtual process ids for some common missing values.

## [1.0.0]

### Fixed

- ProcessDataCollection can now return raw json response.

### Changed

- Minimum Python Version is now 3.7
- Change package metadata
- Changed naming to simpler unique name

### Added

- new function to read events from the inverter
- new sub-command `read-events` for reading events
- download of log data

## [0.2.0] - 2020-11-17

### Changed

- Prepared for PyPI-Publishing
- Allow reading setting values from multiple modules
