# Command Line Interface

## Shell-Commands

The hostname or IP of the Plenticore inverter must be given as argument `--host`. The password might be given direct on the command line with the `--password` option or by file with `--credentials` (`--password-file` is deprecated).

The credentials file is a text file containing at least the following line:

```
password=<password>
```

If you want to use installer authentication instead, the file should contain two lines:

```
master-key=<master key>
service-code=<service code>
```

Alternatively, `--password` and `--service-code` arguments can be used.

After the first login a session id is created and saved in a temporary file. If the command is executed a second time, it is first checked if the session ID is still valid. If not, a new logon attempt is made.

### Display all available process data id's

```shell script
$ pykoplenti --host 192.168.1.100 --password verysecret all-processdata
devices:local/Dc_P
devices:local/DigitalIn
devices:local/EM_State
devices:local/Grid_L1_I
devices:local/Grid_L1_P
~~~
scb:statistic:EnergyFlow/Statistic:Yield:Month
scb:statistic:EnergyFlow/Statistic:Yield:Total
scb:statistic:EnergyFlow/Statistic:Yield:Year
```

The returned ids can be used to query process data values.

### Read process data values

**Read a single value**

```shell script
$ pykoplenti --host 192.168.1.100 --password verysecret read-processdata devices:local/Inverter:State
devices:local/Inverter:State=6.0
```

**Read multiple values (even on different modules)**

```shell script
$ pykoplenti --host 192.168.1.100 --password verysecret read-processdata devices:local/Inverter:State devices:local/EM_State devices:local:pv1/U
devices:local/EM_State=0.0
devices:local/Inverter:State=6.0
devices:local:pv1/U=11.0961999893
```

This is the most efficient way because all process data are fetched with a single HTTP request.

**Read all values off a module**

```shell script
$ pykoplenti --host 192.168.1.100 --password verysecret read-processdata devices:local:pv1
devices:local:pv1/I=0.0058542006
devices:local:pv1/P=-0.11253988
devices:local:pv1/U=10.9401073456
```

### Display all available setting id's

**Display all setting id's**

```shell script
$ pykoplenti --host 192.168.1.100 --password verysecret all-settings
devices:local/ActivePower:ExtCtrl:Enable
devices:local/ActivePower:ExtCtrl:ModeGradientEnable
devices:local/ActivePower:ExtCtrl:ModeGradientFactor
~~~
scb:time/NTPservers
scb:time/NTPuse
scb:time/Timezone
```

**Display only writable setting id's**

```shell script
$ pykoplenti --host 192.168.1.100 --password verysecret all-settings --rw
devices:local/Battery:BackupMode:Enable
devices:local/Battery:DynamicSoc:Enable
devices:local/Battery:MinHomeComsumption
~~~
scb:time/NTPservers
scb:time/NTPuse
scb:time/Timezone
```

### Reading setting values

**Read a single setting value**

```shell script
$ pykoplenti --host 192.168.1.100 --password verysecret read-settings scb:time/Timezone
scb:time/Timezone=Europe/Berlin
```

**Read multiple setting values**
```shell script
$ pykoplenti --host 192.168.1.100 --password verysecret read-settings scb:time/Timezone scb:network/Hostname
scb:time/Timezone=Europe/Berlin
scb:network/Hostname=scb
```

### Writing setting values

```shell script
$ pykoplenti --host 192.168.1.100 --password verysecret write-settings devices:local/Battery:MinSoc=10
```

### REPL

A REPL is provided for simple interactive tests. All methods of the `ApiClient` class can be called. The 
arguments must be given separated by spaces by using python literals. 

```shell script
$ pykoplenti --host 192.168.1.100 repl
(pykoplenti)> get_me
Me(locked=False, active=False, authenticated=False, permissions=[] anonymous=True role=NONE)
(pykoplenti)> get_process_data_values "devices:local" "Inverter:State"
devices:local:
ProcessData(id=Inverter:State, unit=, value=6.0)
```