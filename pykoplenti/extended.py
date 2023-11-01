from abc import ABC, abstractmethod
from collections import ChainMap, defaultdict
from typing import Final, Iterable, Literal, Union

from aiohttp import ClientSession
from pykoplenti import ApiClient, ProcessData, ProcessDataCollection


_VIRT_MODUL_ID: Final = "_virt_"


class _VirtProcessDataItemBase(ABC):
    def __init__(self, processid: str, process_data: dict[str, list[str]]) -> None:
        self.processid = processid
        self.process_data = process_data
        self.available_process_data: dict[str, list[str]] = defaultdict(list)

    def update_actual_process_ids(self, data: dict[str, list[str]]):
        self.available_process_data.clear()
        for mid, pids in self.process_data.items():
            if mid in data:
                for pid in pids:
                    if pid in data[mid]:
                        self.available_process_data[mid].append(pid)

    @abstractmethod
    def get_value(
        self, process_values: dict[str, ProcessDataCollection]
    ) -> ProcessData:
        ...

    @abstractmethod
    def is_available(self) -> bool:
        ...


class _VirtProcessDataItemSum(_VirtProcessDataItemBase):
    def get_value(
        self, process_values: dict[str, ProcessDataCollection]
    ) -> ProcessData:
        values = []
        for mid, pids in self.available_process_data.items():
            for pid in pids:
                values.append(process_values[mid][pid].value)

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
                "scb:statistic:EnergyFlow": [
                    f"Statistic:Yield:{scope}",
                    f"Statistic:EnergyHomeBat:{scope}",
                    f"Statistic:EnergyHomePv:{scope}",
                ]
            },
        )
        self.scope = scope

    def get_value(
        self, process_values: dict[str, ProcessDataCollection]
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
        return len(self.available_process_data) == len(self.process_data)


class _VirtProcessDataManager:
    def __init__(self) -> None:
        self._virt_process_data = [
            _VirtProcessDataItemSum(
                "pv_P",
                {
                    "devices:local:pv1": ["P"],
                    "devices:local:pv2": ["P"],
                    "devices:local:pv3": ["P"],
                },
            ),
            _VirtProcessDataItemEnergyToGrid("Statistic:EnergyGrid:Total", "Total"),
            _VirtProcessDataItemEnergyToGrid("Statistic:EnergyGrid:Year", "Year"),
            _VirtProcessDataItemEnergyToGrid("Statistic:EnergyGrid:Month", "Month"),
            _VirtProcessDataItemEnergyToGrid("Statistic:EnergyGrid:Day", "Day"),
        ]

    def initialize(self, data: dict[str, list[str]]):
        for vpd in self._virt_process_data:
            vpd.update_actual_process_ids(data)

    def adapt_data_response(
        self, process_data: dict[str, list[str]]
    ) -> dict[str, list[str]]:
        virt_process_data: dict[str, list[str]] = {_VIRT_MODUL_ID: []}

        for vpd in self._virt_process_data:
            if vpd.is_available():
                virt_process_data[_VIRT_MODUL_ID].append(vpd.processid)

        return ChainMap(process_data, virt_process_data)

    def adapt_value_request(
        self, process_data: dict[str, list[str]]
    ) -> dict[str, list[str]]:
        result = defaultdict(list, process_data)

        for id in result.pop(_VIRT_MODUL_ID):
            for vpd in self._virt_process_data:
                if vpd.is_available():
                    if id == vpd.processid:
                        vids = vpd.available_process_data
                        break
                    else:
                        raise ValueError(f"No virtual process data '{id}'.")

            # add ids for virtual if they are missing
            for mid, pids in vids.items():
                ids = result[mid]
                for pid in pids:
                    if pid not in ids:
                        ids.append(pid)

        return result

    def adapt_value_response(
        self,
        values: dict[str, ProcessDataCollection],
        request_data: dict[str, list[str]],
    ) -> dict[str, ProcessDataCollection]:
        result = {}

        # add virtual items
        virtual_process_data_values = []
        for id in request_data[_VIRT_MODUL_ID]:
            for vpd in self._virt_process_data:
                if vpd.is_available():
                    virtual_process_data_values.append(vpd.get_value(values))
        result["_virt_"] = ProcessDataCollection(virtual_process_data_values)

        # remove all values which was not requested
        for mid, pdc in values.items():
            if mid in request_data:
                pids = [x for x in pdc.values() if x.id in request_data[mid]]
                if len(pids):
                    result[mid] = ProcessDataCollection(pids)

        return result


class ExtendedApiClient(ApiClient):
    def __init__(self, websession: ClientSession, host: str, port: int = 80):
        super().__init__(websession, host, port)

        self._virt_process_data = _VirtProcessDataManager()
        self._virt_process_data_initialized = False

    async def get_process_data(self) -> dict[str, Iterable[str]]:
        process_data = await super().get_process_data()

        self._virt_process_data.initialize(process_data)
        self._virt_process_data_initialized = True
        return self._virt_process_data.adapt_data_response(process_data)

    async def get_process_data_values(
        self,
        module_id: Union[str, dict[str, Iterable[str]]],
        processdata_id: Union[str, Iterable[str], None] = None,
    ) -> dict[str, ProcessDataCollection]:
        contains_virt_process_data = (
            isinstance(module_id, str) and _VIRT_MODUL_ID == module_id
        ) or (isinstance(module_id, dict) and _VIRT_MODUL_ID in module_id)

        if not contains_virt_process_data:
            # short-cut if no virtual process is requested
            return await super().get_process_data_values(module_id, processdata_id)

        process_data: dict[str, list[str]] = {}
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
        elif isinstance(module_id, dict) and processdata_id is None:
            process_data.update(module_id)
        else:
            raise TypeError("Invalid combination of module_id and processdata_id.")

        if not self._virt_process_data_initialized:
            pd = await self.get_process_data()
            self._virt_process_data.initialize(pd)
            self._virt_process_data_initialized = True

        process_values = await super().get_process_data_values(
            self._virt_process_data.adapt_value_request(process_data)
        )
        return self._virt_process_data.adapt_value_response(
            process_values, process_data
        )
