# [neOCampus] LoRaWAN powermeter #
__________________________________

This app. stems from neOCampus LoRaWAN applications. It allows you to read data from a modbus connected powermeter
and to send those Data to the LoRaWAN server through a RN2483 end-device.

### Settings ###
According to your current setup, modify file(s):
```
settings/settings.py
```

### Launch application ###
To launch this app with defaukts settings:
```
./app.py
```

*Option*
    - you can disable duty-cycle either through settings or cli
        ./app.py -d --set-dcycle=20

