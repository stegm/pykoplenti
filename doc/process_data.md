# Process Data

Here are some notes about process data which might not be clear at first:

| Process Data | Modbus | Description | Comment |
|--------------|--------|-------------|---------|
| devices:local/Dc_P | 0x64 | Total DC power | This also includes battery |
| scb:statistic:EnergyFlow/Statistic:EnergyChargePv:Total | 0x416 |  Total DC charge energy (DC-side to battery) | |
| scb:statistic:EnergyFlow/Statistic:EnergyDischarge:Total | 0x418 | Total DC discharge energy (DC-side from battery) | |
| scb:statistic:EnergyFlow/Statistic:EnergyChargeGrid:Total | 0x41A | Total AC charge energy (AC-side to battery) | |
| scb:statistic:EnergyFlow/Statistic:EnergyDischargeGrid:Total | 0x41C | Total AC discharge energy (battery to grid) | |
| scb:statistic:EnergyFlow/Statistic:EnergyChargeInvIn:Total | 0x41E | Total AC charge energy (grid to battery) | |
