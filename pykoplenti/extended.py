"""Extended ApiClient which provides virtual process data values."""

from abc import ABC, abstractmethod
from collections import ChainMap, defaultdict
from typing import Final, Iterable, Literal, Mapping, MutableMapping, Union

from aiohttp import ClientSession

from .api import ApiClient
from .model import ProcessData, ProcessDataCollection

_VIRT_MODUL_ID: Final = "_virt_"


class _VirtProcessDataItemBase(ABC):
    """Base class for all virtual process data items."""

    def __init__(self, processid: str, process_data: dict[str, set[str]]) -> None:
        self.processid = processid
        self.process_data = process_data
        self.available_process_data: dict[str, set[str]] = {}

    def update_actual_process_ids(
        self, available_process_ids: Mapping[str, Iterable[str]]
    ):
        """Update which process data for this item are available."""
        self.available_process_data.clear()
        for module_id, process_ids in self.process_data.items():
            if module_id in available_process_ids:
                matching_process_ids = process_ids.intersection(
                    available_process_ids[module_id]
                )
                if len(matching_process_ids) > 0:
                    self.available_process_data[module_id] = matching_process_ids

    @abstractmethod
    def get_value(
        self, process_values: Mapping[str, ProcessDataCollection]
    ) -> ProcessData:
        ...

    @abstractmethod
    def is_available(self) -> bool:
        ...


class _VirtProcessDataItemSum(_VirtProcessDataItemBase):
    def get_value(
        self, process_values: Mapping[str, ProcessDataCollection]
    ) -> ProcessData:
        values: list[float] = []
        for module_id, process_ids in self.available_process_data.items():
            values += (process_values[module_id][pid].value for pid in process_ids)

        return ProcessData(id=self.processid, unit="W", value=sum(values))

    def is_available(self) -> bool:
        return len(self.available_process_data) > 0


class _VirtProcessDataItemEnergyToGrid(_VirtProcessDataItemBase):
    def __init__(
        self, processid: str, scope: Literal["Total", "Year", "Month", "Day"]
    ) -> None:
        super().__init__(
            processid,
            {
                "scb:statistic:EnergyFlow": {
                    f"Statistic:Yield:{scope}",
                    f"Statistic:EnergyHomeBat:{scope}",
                    f"Statistic:EnergyHomePv:{scope}",
                }
            },
        )
        self.scope = scope

    def get_value(
        self, process_values: Mapping[str, ProcessDataCollection]
    ) -> ProcessData:
        statistics = process_values["scb:statistic:EnergyFlow"]
        energy_yield = statistics[f"Statistic:Yield:{self.scope}"].value
        energy_home_bat = statistics[f"Statistic:EnergyHomeBat:{self.scope}"].value
        energy_home_pv = statistics[f"Statistic:EnergyHomePv:{self.scope}"].value

        return ProcessData(
            id=self.processid,
            unit="Wh",
            value=energy_yield - energy_home_pv - energy_home_bat,
        )

    def is_available(self) -> bool:
        return self.available_process_data == self.process_data


class _VirtProcessDataManager:
    """Manager for all virtual process data items."""

    def __init__(self) -> None:
        self._virt_process_data: Iterable[_VirtProcessDataItemBase] = [
            _VirtProcessDataItemSum(
                "pv_P",
                {
                    "devices:local:pv1": {"P"},
                    "devices:local:pv2": {"P"},
                    "devices:local:pv3": {"P"},
                },
            ),
            _VirtProcessDataItemEnergyToGrid("Statistic:EnergyGrid:Total", "Total"),
            _VirtProcessDataItemEnergyToGrid("Statistic:EnergyGrid:Year", "Year"),
            _VirtProcessDataItemEnergyToGrid("Statistic:EnergyGrid:Month", "Month"),
            _VirtProcessDataItemEnergyToGrid("Statistic:EnergyGrid:Day", "Day"),
        ]

    def initialize(self, available_process_data: Mapping[str, Iterable[str]]):
        """Initialize the virtual items with the list of available process ids."""
        for vpd in self._virt_process_data:
            vpd.update_actual_process_ids(available_process_data)

    def adapt_process_data_response(
        self, process_data: dict[str, list[str]]
    ) -> Mapping[str, list[str]]:
        """Adapt the reponse of reading process data."""
        virt_process_data: dict[str, list[str]] = {_VIRT_MODUL_ID: []}

        for vpd in self._virt_process_data:
            if vpd.is_available():
                virt_process_data[_VIRT_MODUL_ID].append(vpd.processid)

        return ChainMap(process_data, virt_process_data)

    def adapt_process_value_request(
        self, process_data: Mapping[str, Iterable[str]]
    ) -> Mapping[str, Iterable[str]]:
        """Adapt the request for process values."""
        result: MutableMapping[str, set[str]] = defaultdict(set)

        for mid, pids in process_data.items():
            result[mid].update(pids)

        for requested_virtual_process_id in result.pop(_VIRT_MODUL_ID):
            for virtual_process_data in self._virt_process_data:
                if virtual_process_data.is_available():
                    if requested_virtual_process_id == virtual_process_data.processid:
                        # add ids for virtual if they are missing
                        for (
                            mid,
                            pids,
                        ) in virtual_process_data.available_process_data.items():
                            result[mid].update(pids)
                        break
            else:
                raise ValueError(
                    f"No virtual process data '{requested_virtual_process_id}'."
                )

        return result

    def adapt_process_value_response(
        self,
        values: Mapping[str, ProcessDataCollection],
        request_data: Mapping[str, Iterable[str]],
    ) -> Mapping[str, ProcessDataCollection]:
        """Adapt the reponse for process values."""
        result = {}

        # add virtual items
        virtual_process_data_values = []
        for id in request_data[_VIRT_MODUL_ID]:
            for vpd in self._virt_process_data:
                if vpd.processid == id:
                    virtual_process_data_values.append(vpd.get_value(values))
        result["_virt_"] = ProcessDataCollection(virtual_process_data_values)

        # add all values which was requested but not the extra ids for the virtual ids
        for mid, pdc in values.items():
            if mid in request_data:
                pids = [x for x in pdc.values() if x.id in request_data[mid]]
                if len(pids) > 0:
                    result[mid] = ProcessDataCollection(pids)

        return result


class ExtendedApiClient(ApiClient):
    """Extend ApiClient with virtual process data."""

    def __init__(self, websession: ClientSession, host: str, port: int = 80):
        super().__init__(websession, host, port)

        self._virt_process_data = _VirtProcessDataManager()
        self._virt_process_data_initialized = False

    async def get_process_data(self) -> Mapping[str, Iterable[str]]:
        process_data = await super().get_process_data()

        self._virt_process_data.initialize(process_data)
        self._virt_process_data_initialized = True
        return self._virt_process_data.adapt_process_data_response(process_data)

    async def get_process_data_values(
        self,
        module_id: Union[str, Mapping[str, Iterable[str]]],
        processdata_id: Union[str, Iterable[str], None] = None,
    ) -> Mapping[str, ProcessDataCollection]:
        contains_virt_process_data = (
            isinstance(module_id, str) and _VIRT_MODUL_ID == module_id
        ) or (isinstance(module_id, dict) and _VIRT_MODUL_ID in module_id)

        if not contains_virt_process_data:
            # short-cut if no virtual process is requested
            return await super().get_process_data_values(module_id, processdata_id)

        process_data: dict[str, Iterable[str]] = {}
        if isinstance(module_id, str) and processdata_id is None:
            process_data[module_id] = []
        elif isinstance(module_id, str) and isinstance(processdata_id, str):
            process_data[module_id] = [processdata_id]
        elif (
            isinstance(module_id, str)
            and processdata_id is not None
            and hasattr(processdata_id, "__iter__")
        ):
            process_data[module_id] = list(processdata_id)
        elif isinstance(module_id, Mapping) and processdata_id is None:
            process_data.update(module_id)
        else:
            raise TypeError("Invalid combination of module_id and processdata_id.")

        if not self._virt_process_data_initialized:
            pd = await self.get_process_data()
            self._virt_process_data.initialize(pd)
            self._virt_process_data_initialized = True

        process_values = await super().get_process_data_values(
            self._virt_process_data.adapt_process_value_request(process_data)
        )
        return self._virt_process_data.adapt_process_value_response(
            process_values, process_data
        )
