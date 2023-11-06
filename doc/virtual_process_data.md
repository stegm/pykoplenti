# Virtual Process Data

Currently the inverter API is missing some interessting values, which are now provided by the class `ExtendedApiClient`. These virtual items are computed by means of other process items.

All virtual process items are in the module `_virt_`.

Note: This feature is experimental and might change in the next version.

| process id                  | description |
|-----------------------------|-------------|
| pv_P                        | Sum of all PV DC inputs (from `devices:local:pv1/P` + `devices:local:pv2/P` + `devices:local:pv3/P`) |
| Statistic:EnergyGrid:Total  | Total energy delivered to grid (from `Statistic:Yield:Total` - `Statistic:EnergyHomeBat:Total` - `Statistic:EnergyHomePv:Total`) |
| Statistic:EnergyGrid:Year   | Total energy delivered to grid (from `Statistic:Yield:Year` - `Statistic:EnergyHomeBat:Year` - `Statistic:EnergyHomePv:Year`) |
| Statistic:EnergyGrid:Month  | Total energy delivered to grid (from `Statistic:Yield:Month` - `Statistic:EnergyHomeBat:Month` - `Statistic:EnergyHomePv:Month`) |
| Statistic:EnergyGrid:Day    | Total energy delivered to grid (from `Statistic:Yield:Day` - `Statistic:EnergyHomeBat:Day` - `Statistic:EnergyHomePv:Day`) |
