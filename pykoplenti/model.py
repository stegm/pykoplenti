from datetime import datetime
from typing import Final, Iterator, Mapping, Optional

import pydantic
from pydantic import BaseModel, Field


class MeData(BaseModel):
    """Represent the data of the 'me'-request."""

    is_locked: bool = Field(alias="locked")
    is_active: bool = Field(alias="active")
    is_authenticated: bool = Field(alias="authenticated")
    permissions: list[str] = Field()
    is_anonymous: bool = Field(alias="anonymous")
    role: str


class VersionData(BaseModel):
    """Represent the data of the 'version'-request."""

    api_version: str
    hostname: str
    name: str
    sw_version: str


class ModuleData(BaseModel):
    """Represents a single module."""

    id: str
    type: str


class ProcessData(BaseModel):
    """Represents a single process data."""

    id: str
    unit: str
    value: float


class ProcessDataCollection(Mapping):
    """Represents a collection of process data value."""

    def __init__(self, process_data: list[ProcessData]):
        self._process_data = process_data

    def __len__(self) -> int:
        return len(self._process_data)

    def __iter__(self) -> Iterator[str]:
        return (x.id for x in self._process_data)

    def __getitem__(self, item) -> ProcessData:
        try:
            return next(x for x in self._process_data if x.id == item)
        except StopIteration:
            raise KeyError(item) from None

    def __eq__(self, __other: object) -> bool:
        if not isinstance(__other, ProcessDataCollection):
            return False

        return self._process_data == __other._process_data

    def __str__(self):
        return "[" + ",".join(str(x) for x in self._process_data) + "]"

    def __repr__(self):
        return (
            "ProcessDataCollection(["
            + ",".join(repr(x) for x in self._process_data)
            + "])"
        )


class SettingsData(BaseModel):
    """Represents a single settings data."""

    min: Optional[str]
    max: Optional[str]
    default: Optional[str]
    access: str
    unit: Optional[str]
    id: str
    type: str


class EventData(BaseModel):
    """Represents an event of the inverter."""

    start_time: datetime
    end_time: datetime
    code: int
    long_description: str
    category: str
    description: str
    group: str
    is_active: bool


# pydantic version specific code
# In pydantic 2.x `parse_obj_as` is no longer supported. To stay compatible to
# both version a small wrapper function is used.

if pydantic.VERSION.startswith("2."):
    from pydantic import TypeAdapter

    _process_list_adapter: Final = TypeAdapter(list[ProcessData])

    def process_data_list(json) -> list[ProcessData]:
        """Process json as a list of ProcessData objects."""
        return _process_list_adapter.validate_python(json)

else:
    from pydantic import parse_obj_as

    def process_data_list(json) -> list[ProcessData]:
        """Process json as a list of ProcessData objects."""
        return parse_obj_as(list[ProcessData], json)
