#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# powermeter board demo settings file
#
# Thiebolt F.   mar.20  adapted for tutorial usage
# Thiebolt F.   sep.19  added CNF/UNCF option when sending messages
# Thiebolt F.   apr.19  initial release
#



# #############################################################################
#
# Import zone
#
import logging


# #############################################################################
#
# powermeter settings
#

# General

# Directories


#
# RN2483 hardware
# Note: we support two hardware options:
#   - RN2483 directly connected to Raspberry Pi's GPIO (serial + GPIO4 for reset)
#   - RN2483 as a USB module (hence ttyUSB0 on linux systems)

# USB connected RN2483
serial_link         = "/dev/ttyUSB0"
'''
# [alternative] RN2483 within Raspberry Pi
serial_link         = "/dev/ttyS0"
reset_pin           = 4             # GPIO pin ties to RN2483's RST
'''
#serial_link_speed   = 57600        # default


#
# LoRaWAN
deveui = "<your DEVEUI>"
appeui = "<your AAPEUI>"
appkey = "<your APPEUI's secret key>"

'''
# Override 1% duty-cycle
disable_adr         = True          # disable ADR mode
ask_cnf             = False         # do not ask the gateway to ack for reception of our messages (Default is True)
duty_cycle          = 80            # percents (default is 1%)
data_rate           = 3             # 0:SF12/125kHz(default) 5:SF7/125kHz   Note: this is for DATA exchanges (i.e not JOIN)
data_sf             = "SF9"         # ok, a bit odd that we ought to specify it while it oughts to get dervied from data_rate :|
'''


#
# Modbus settings
'''
modbus_link         = "/dev/ttyUSB0"    # RS-485 USB adapter
modbus_link_speed   = 9600

modbus_addr         = [ 63 ]            # Modbus adresse of devices
#modbus_debug        = True              # enable modbus serial link debug messages
'''


#
# neOCampus exchange loop timer (seconds)
loraTimer   = 60
#loraTimer   = 300


#
# Logging
#log_level = logging.INFO
log_level = logging.DEBUG


