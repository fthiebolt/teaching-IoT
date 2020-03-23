#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Modbus LoRaWAN power meter gateway
#
# Notes:
# - to send data back to our RN2483, external application ought to publish to
#   <topic>/<deveui>/command <-- {'data':'<hex values>'}
#   e.g TestTopic/lora/<DEVEUI>/command <-- {'data':'F88F'}
#
# Required python packages
#   pip3 install hexdump
#   pip3 install --upgrade pyserial
#
# -----------------------------------------------------------------------------
# Notes:
# -----------------------------------------------------------------------------
#
# F.Thiebolt    apr.19  heavily based on my RN2483_OTAA.py
#



# #############################################################################
#
# Import zone
#
import os
import signal
import sys
import time
from datetime import datetime

# GPIO (for optional reset_pin)
import RPi.GPIO as GPIO

# CLI options
import argparse

# Multi-threaded tests
import threading

# Serial comms
import serial

# hex dump
from hexdump import hexdump


#
# import settings
from settings import settings

#
# import logging
import logging
from settings.logger import log, init_remote_logger, setLogLevel, getLogLevel

#
# import radio module
from radio.RN2483 import RN2483

#
# import ModbusBackend
#from energy_meters.modbus import ModbusBackend



# #############################################################################
#
# Global Variables
#

# modbus backend
#_backend        = None

# Shutdown event for all threads, modules etc
_shutdownEvent  = None



# #############################################################################
#
# Functions
#


#
# Function ctrlc_handler
def ctrlc_handler(signum, frame):
    global _shutdownEvent
    print("<CTRL + C> action detected ...");
    _shutdownEvent.set()


#
# Function about CLI parameters
def help():
    print("TO BE DEFINED :|")
    sys.exit(1)



# #############################################################################
#
# Class
#



# #############################################################################
#
# MAIN
#

def main():

    # Global variables
    global _shutdownEvent

    #
    print("\n###\nLoRaWAN powermeter demo based on RN2483")
    print("###")

    # create threading.event
    _shutdownEvent = threading.Event()

    # Trap CTRL+C (kill -2)
    signal.signal(signal.SIGINT, ctrlc_handler)

    # Parse arguments
    parser = argparse.ArgumentParser(
                         description="LoRaWAN powermeter based on RN2483 \
                         \n Hit <ENTER> to terminate program." )

    parser.add_argument( '-p', '--port', type=str,
                         dest="serial_link",nargs='?',
                         help="Serial port to use, eg. /dev/ttyAMA0." )

    parser.add_argument( '-s', '--speed', type=int,
                         dest="serial_link_speed",nargs='?',
                         help="Absolute path to labels file." )

    parser.add_argument( '--reset-pin', type=int,
                         dest="reset_pin",nargs='?',
                         help="RPi's GPIO connected to RST pin of RN2483." )

    parser.add_argument( '--set-dcycle', type=int,
                         dest="duty_cycle",nargs='?',
                         help="Set duty cycle percent from 0 to 100 on all channels." )

    # debug mode
    parser.add_argument( '-d', '--debug', action="store_true",
                         help="Toggle debug mode (True as default)." )

    ARGS = parser.parse_args()
    #print(ARGS)

    # logging
    if( ARGS.debug is True ):
        print("\n[DBG] DEBUG mode activated ... ") 
        setLogLevel(logging.DEBUG)
    else:
        print("\n[LOG] level set to %d" % int(settings.log_level) )
        setLogLevel(settings.log_level)

    # Setup GPIOs
    GPIO.setmode(GPIO.BCM)


    '''
    #
    # Modbus initialisation
    log.info("Instantiate and enable modbus backend ...")
    try:
        kwargs = dict()
        kwargs['shutdown_event'] = _shutdownEvent
        if( hasattr(settings, 'modbus_debug') is True ):
            kwargs['modbus_debug'] = settings.modbus_debug
        _backend = ModbusBackend(settings.modbus_link, settings.modbus_link_speed, **kwargs)
        _backend.enable()
    except Exception as ex:
        log.error("unable to initialise Modbus backend: " + str(ex) )
        raise ex
    time.sleep(1)
    '''


    #
    # LoRaWAN
    #
    # RN2483 serial initialisation
    log.info("Starting RN2483 initialisation ...");
    try:
        # instantiate device with optional specific configuration
        _deviceConfig = dict()
        # register shurdownEvent
        _deviceConfig['shutdown_event'] = _shutdownEvent
        # enable/disable ADR mode
        _deviceConfig['adr'] = True
        if( hasattr(settings, 'disable_adr') is True ):
            if settings.disable_adr is True:
                _deviceConfig['adr'] = False
        # set data exchange DataRate mode 0:SF12/125kHz to 5:SF7/125kHz
        _deviceConfig['dr'] = 0     # SF12/125kHz
        if( hasattr(settings, 'data_rate') is True ):
            _deviceConfig['dr'] = settings.data_rate
        # set data exchange DataRate spreading factor (default is SF12)
        if( hasattr(settings, 'data_sf') is True ):
            _deviceConfig['sf'] = settings.data_sf
        # optional reset pin
        if( ARGS.reset_pin is not None ):
            _deviceConfig['reset_pin'] = ARGS.reset_pin
        elif( hasattr(settings, 'reset_pin') is True ):
            _deviceConfig['reset_pin'] = settings.reset_pin
        # optional duty cycle
        if( ARGS.duty_cycle is not None ):
            _deviceConfig['duty_cycle'] = ARGS.duty_cycle
        elif( hasattr(settings, 'duty_cycle') is True ):
            _deviceConfig['duty_cycle'] = settings.duty_cycle

        #
        # instantiate LoRaWAN device
        device = RN2483( ARGS.serial_link if ARGS.serial_link is not None else settings.serial_link,
                         ARGS.serial_link_speed if ARGS.serial_link_speed is not None else settings.serial_link_speed,
                         **_deviceConfig );

        # tell we're on external power supply
        device.batlvl = 0

    except Exception as ex:
        log.error("### ERROR on RN2483 instantiation: " + str(ex))
        raise ex
    log.info("RN2483 successfully instantiated :)")
    
    # RN2483 LoRaWAN initialisation
    log.info("Starting LoRaWAN initialisation ...");
    try:
        # [RADIO] LoRa parameters
        #device.mod      = 'lora'    # default modulation: LoRa
        #device.freq     = int(868.1*1000000)  # default to 868.1MHz
        device.pwr      = 14
        #device.sf       = 'sf7'     # default sf12
        #device.cr       = '4/8'     # default 4/5
        #device.bw       = 250       # default 125kHz
        #device.crc      = 'off'     # default on

        # [MAC] LoRaWAN parameters
        device.devEUI   = settings.deveui
        device.appEUI   = settings.appeui
        device.appKEY   = settings.appkey

        # save parameters
        #device.loraMacSave()

    except Exception as ex:
        log.error("### LoRaWAN initialization error: " + str(ex))
        raise ex
    log.info("LoRaWAN setup successful :)")
    print(device)
    time.sleep(2)


    #
    # main loop
    txData = None

    while( not _shutdownEvent.is_set() ):
        try: 
            # need to join ?
            if( device.isConnected() is not True ):
                # activate OTAA join
                device.connect(mode='otaa')
                # are we connected ?
                if( device.isConnected() is not True ):
                    time.sleep(5)
                    continue
                # print device detailed status
                print(device)
                log.debug("sleeping a bit before continuing ...")
                time.sleep(5)

            _startTime = datetime.now()


            #
            # TX some data
            # TODO: make use of optional port :)
            log.info("Sending some data ...")

            txData = "hello from RN2483!"
            print("MyData = %s" % str(txData) )

            #
            # TX messages with or without acknowledge
            # Note: if 1% duty-cycle is disabled, best is to ask for acknowledge
            _ask4cnf = True
            if( hasattr(settings, 'ask_cnf') is True ):
                _ask4cnf=settings.ask_cnf
            if( device.transmitData( str(txData), ack=_ask4cnf ) is not True ):
                log.debug("tx command not accepted by LoRaWAN stack :(")
                log.debug("... sleeping a bit before retrying ...")
                time.sleep(7)
                continue


            _txAnswer = None
            # LoRaWAN Class A | wait for some data in return from previous transmit
            log.info("Waiting for some data ...")
            while( (datetime.now()-_startTime).total_seconds() < settings.loraTimer and not _shutdownEvent.is_set() ):
                print("_*_", end='', flush=True)
                rxData = device.receiveData( )
                if( rxData is None ): continue
                if( not rxData.endswith('\r\n') ):
                    log.warning("Partial data received !!\n\t'%s'" % str(rxData) )
                    time.sleep(1)
                    continue
                rxData = rxData.rstrip('\r\n')
                if( _txAnswer is not None ):
                    # this RX1 or RX2 or class C device ?
                    log.info("Received data = '%s'" % str(rxData))
                    time.sleep(1)
                    continue
                # TX answer received
                log.info("TX answer received: '%s'" % rxData)
                if( rxData == 'mac_tx_ok' ):
                    _txAnswer = rxData
                    continue
                elif( rxData.startswith('mac_rx') ):
                    # RX1 or RX2 slots received data

                    _rxFields = rxData.split()
                    print("\n\tPort[%d] answer received: '%s'" % (int(_rxFields[1]),str(_rxFields[2:])) )                    

                    # TODO: process incomming data

                    print("\tTODO: process incoming data!")
                    _txAnswer = rxData
                    time.sleep(1)
                    continue
                elif( rxData == 'mac_err' ):
                    # failure to send
                    log.warning("'mac_err' ... failed to transmit data ... mac status = 0x%08X ... try to resend :|" % (device.macStatus))
                    time.sleep(4)
                    break
                elif( rxData.startswith('invalid_data_len') ):
                    # payload too large
                    log.warning("oversized payload ... (ADR mode??) ... try to resend :|")
                    time.sleep(4)
                    break
                elif( rxData.startswith('invalid') ):
                    # [aug.19] let's consider this as a warning ...
                    log.warning("there's something wrong in the TX process ... ... mac status = 0x%08X ... try to resend" % (device.macStatus))
                    time.sleep(4)
                else:
                    log.warning("unknwown TX answer '%s' ?!?! ... continuing" % rxData)
                    time.sleep(1)                    

        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            log.error("exception '%s'(line %d): " % (exc_type,exc_tb.tb_lineno) + str(ex))
            time.sleep(3)
            continue

    # destroy instance
    log.info("ending LoRaWAN ops ...");
    del(device)

    # GPIO cleanup
    GPIO.cleanup()


# Execution or import
if __name__ == "__main__":

    # Start executing
    main()

# The END - Jim Morrison 1943 - 1971
#sys.exit(0)

