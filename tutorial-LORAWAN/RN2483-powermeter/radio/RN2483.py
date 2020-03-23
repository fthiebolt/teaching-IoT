#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# RN2483 class
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
# - todo: correct SF @ __repr__
# -----------------------------------------------------------------------------
#
# F.Thiebolt    sep.19  added support for data spreading factor
# F.Thiebolt    aug.19  started to add support for FWrev 1.0.5
# F.Thiebolt    apr.19  heavily based on RN2483_OTAA.py
#



# #############################################################################
#
# Import zone
#
import os
import signal
import syslog
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
# import logging
from settings.logger import log




# #############################################################################
#
# Global Variables
#



# #############################################################################
#
# Functions
#



# #############################################################################
#
# Class
#
class RN2483(object):
    ''' RN2483 manager '''

    # Class attributes
    DEFAULT_SERIAL_LINK     = "/dev/ttyUSB0"
    DEFAULT_SERIAL_SPEED    = 57600
    DEFAULT_SERIAL_BITS     = serial.EIGHTBITS
    DEFAULT_SERIAL_PARITY   = serial.PARITY_NONE
    DEFAULT_SERIAL_STOP     = serial.STOPBITS_ONE
    DEFAULT_SERIAL_TIMEOUT  = 1.2   # serial read timeout seconds

    LORA_ON_OFF             = ['on','off']
    LORA_SYS_SLEEP          = [100, 2**32]      # sleep for 100ms to ...
    LORA_JOIN_MODES         = ['otaa','abp']
    LORA_RADIO_MODULATION   = ['lora','fsk']
    LORA_RADIO_TX_POWER     = list(range(-3,14+1))
    LORA_RADIO_FREQUENCIES  = [ 868.1, 868.3, 868.5, 867.1, 867.3, 867.5, 867.7, 867.9, 868.8, 869.525 ] # 868.8 for 'fsk' modulation, 869.525 is RX2 downlink
    LORA_SPREAD_FACTOR      = [ "sf"+str(x) for x in range(7,12+1) ]  # sf7 faster comm, sf12 slower comm
    LORA_CODING_RATE        = ['4/5','4/6','4/7','4/8'] # 4/5 faster comm, 4/8 slower comm
    LORA_BANDWIDTH          = [ 126, 250, 500 ]     # kHz
    LORA_RX_WATCHDOG        = 2**32         # maximum (ms) timeout value for receiving a message. Ought to be set to 0 for continuous receive mode
    LORA_TX_PORTS_RNG       = range(1,223+1)  # TX port [1..223]
    LORA_BAT_LVL_RNG        = range(0,255+1)  # 0:external power supply, 1:low-level, 254:full, 255:unable to measure

    # attributes
    _addons         = None      # dict() of additional parameters
    _link           = None      # opened serial link
    serial_port     = None
    serial_speed    = 0
    _serial_lock    = None      # serial link locking: to protect against read and reset at the same time from different threads
    _gpio_rst       = None      # optional GPIO pin to reset the device (otherwise through DTR line)

    _fw_rev         = None      # Firmware revision <major>.<med>.<minor>, e.g 1.0.5 as a list

    _dcycle         = 799       # eight channels to share for 1% --> 0.125% each channel --> (100/duty-cycle)-1
    _data_rate      = None      # data rate mode for DATA exchanges (i.e not during JOIN ---DR:0 (SF12) as default)
    _data_sf        = None      # data spreading factor for DATA exchanges (i.e not during JOIN)

    _condition      = None      # threading condition
    _thread         = None      # thread to handle recv buffer

    _shutdown_event = None

    ''' RADIO LoRa attributes (properties)
    mod         # LoRa modulation is either 'lora' or 'fsk'
    freq        # frequency to use (channel 0-2 to join)
    pwr         # radio module TX power
    sf          # spreading factor, a measure for the (relative) number of symbols (chirp) per bits to encode
                    the more you spread (sf12) the more you are resistant but the slower you go
    crc         # checksum 'on' or 'off'
    iqi         # inverting bits (to avoid gateways to ta to each others)
    cr          # coding rate CR, refers to the proportion of transmitted bits that actually carry information.
                    So if CR is 4/8 we are transmitting twice as many bits as the ones containing information.
    bw          # bandwidth BW, meaning the difference in minimum and maximum frequency spread centered on freq
    wdt         # watchdog, for continuous reception, ought to be set to 0
    '''

    # LoRaWAN attributes
    # Note: most of them are 'properties' but we keep those as rgular attributes
    #   because we're unable to read them from RN2483 (are part of write-only commands)
    _appKEY         = None
    _batlvl         = None


    # Initialization
    def __init__(self, port=None, speed=0, shutdown_event=None, *args, **kwargs):

        log.info("Initializing '%s' module ..." % __class__.__name__)
        self._addons        = None

        self._link          = None
        self.serial_lock    = None

        self._appKEY        = None
        self._batlvl        = None

        self._data_rate     = None

        self._shutdown_event    = shutdown_event

        if kwargs is not None:
            self._addons = kwargs

        if port is not None:
            self.serial_port = port
            try:
                self.serial_speed = int(speed) if int(speed)!=0 else __class__.DEFAULT_SERIAL_SPEED
            except ValueError as ex:
                log.error("link_speed '%s' is not an integer ... aborting" % (str(speed)) )
                raise ex

        # reset_pin option ?
        if kwargs.get('reset_pin',None) is not None:
            self._gpio_rst = int(kwargs['reset_pin'])
            GPIO.setup(self._gpio_rst, GPIO.HIGH)   # set HIGH before OUT mode to avoid spurious RST on RN2483
            GPIO.setup(self._gpio_rst, GPIO.OUT)
            log.info("\tsetting GPIO '%d' as reset pin ..." % self._gpio_rst )
            # ... and remove from dict
            kwargs.pop('reset_pin',None)

        # thread related initialization
        self._condition = threading.Condition()
        self._thread = None

        # check link to test presence of serial adapter
        # and presence of a RN2483 module
        self.start_serial()
        if( self._fw_rev is None ):
            raise Exception("unable to read FW revision of RN2483 module ?!?!")

        # radioModule factory reset settings
        self.loraFactoryReset()

        # LoRaWAN setup
        self._command("mac reset 868", True)    # configure radio for 868MHz ops
        self._command("mac set retx 2", True)   # for confirmed type messages, number of retransmissions until gateway ack
        self._command("mac set dr 0", True)     # set data rate to 0:SF12/125kHz (slowest) 5:SF7/125kHz (fastest)
        self._command("mac set linkchk 600", True)  # link check process interval
        #self._command("mac set ar on", True)    # automatic reply on downlink reception

        # check for extra parameters
        if( self._addons ):
            for key,val in self._addons.items():
                # check for 'ADR'
                if( key.lower() == "adr" ):
                    if val is True:
                        log.info("Enabling Adaptative Data Rate (ADR) ...")
                        self._command("mac set adr on")
                    else:
                        log.info("Disabling Adaptative Data Rate (ADR) ...")
                        self._command("mac set adr off")
                    continue
                # check for 'DR' (i.e data rate)
                if( key.lower() == "dr" ):
                    log.info("Set DataRate ...")
                    #self._command("mac set dr %d" % int(val))
                    self._data_rate = int(val)
                    continue
                # check for 'duty_cycle'
                if( key.lower() == "duty_cycle" ):
                    log.info("Override duty cycle default value ...")
                    self._dcycle = int(100/int(val))-1
                    continue
                # check for 'SF' (i.e data spreading factor)
                if( key.lower() == "sf" ):
                    if val.lower() not in __class__.LORA_SPREAD_FACTOR:
                        log.error("Specified SF '%s' not supported" % val.lower())
                        continue
                    log.info("Set SpreadingFactor ...")
                    #self._command("radio set sf %s" % val)
                    self._data_sf = val.lower()
                    continue
                log.debug("unknwon _addon parameter '%s' ?!?!" % str(key) )

        # end of setup
        time.sleep(0.5)


    # Destructor
    def __del__(self):
        ''' destructor method '''
        log.info("... call for destructor of '%s' instance ..." % __class__.__name__ )

        # close LoRaWAN exchange
        # TODO!

        # stop serial link
        self.stop_serial()

        log.info("'%s' instance deleted" % __class__.__name__ )


    # nice object representation
    def __repr__(self):
        buf = str()
        buf += "[LoRa] " + self._command("sys get ver") + "\n"
        buf += "  adr    : " + self._command("mac get adr") + "\n"
        #TODO: correct SF since it may get set from CLI option!!
        buf += " [RADIO] settings" + "\n"
        buf += "  mod    : " + str(self.modulation) + "\n"
        buf += "  freq   : " + str(self.freq) + "\n"
        buf += "  pwr    : " + str(self.pwr) + "\n"
        buf += "  sf     : " + self._command("radio get sf") + "\n"
        buf += "  crc    : " + str(self.crc) + "\n"
        buf += "  iqi    : " + str(self.iqi) + "\n"
        buf += "  cr     : " + str(self.cr) + "\n"
        buf += "  bw     : " + str(self.bw) + "\n"
        buf += "  wdt    : " + str(self.wdt) + "\n"
        buf += " [MAC] settings" + "\n"
        buf += "  class  : " + str(self.classDevice) + "\n"
        buf += "  devEUI : 0x" + str(self.devEUI) + "\n"
        buf += "  appEUI : 0x" + str(self.appEUI) + "\n"
        buf += "  appKEY : 0x" + str(self.appKEY) + "\n"
        buf += "  hwEUI  : 0x" + self._command("sys get hweui") + "\n"
        # advanced parameters
        if( self.isConnected() ):
            buf += "  pwridx : " + self._command("mac get pwridx") + "\n"
            buf += "  drates : " + self._command("mac get dr") + "\n"
            buf += "  ADRate : " + self._command("mac get adr") + "\n"
            for ch in range(0,15+1):
                _chStatus = self._command("mac get ch status %d" % ch)
                if( _chStatus != "on" ):
                    buf += ("    channel %d off" % ch) + "\n"
                    continue
                _freq = float(self._command("mac get ch freq %d" % ch))/1000000.0
                _rawDcycle = float(self._command("mac get ch dcycle %d" % ch))
                _percentDcycle = float(100.0/(_rawDcycle + 1))
                buf += ("    channel %d  freq %.1f  dcycle %.3f" % (ch,_freq,_percentDcycle)) + "\n"

        return buf


    def _is_fwrev_ge(self, val):
        ''' check if current fw release match is Greater or Equal to the one specified as a parameter. '''
        _cur_fwrev = self._fw_rev[:]
        # extract integers
        try:
            _expected_fwrev = [ int(x) for x in val.split('.') ]
        except Exception as ex:
            log.error("unable to parse fw_rev '%s' " + str(ex) )
            raise ex

        # extends list to match each others
        difflen = len(_cur_fwrev) - len(_expected_fwrev)
        if( difflen > 0 ):
            _expected_fwrev.extend( [0] * abs(difflen) )
        elif( difflen < 0 ):
            _cur_fwrev.extend( [0] * abs(difflen) )

        # check fw revisions
        for cur,expected in zip(_cur_fwrev,_expected_fwrev):
            if( cur > expected ):
                return True
            elif( cur < expected ):
                return False
        # revisions are the same
        return True


    def start_serial(self):
        ''' verify serial link is valid ... and a RN2483 is connected to '''
        if( self._link is not None ):
            log.warning("# serial link is already active !")
            return

        try:
            # warning: port is immediately opened on link creation
            log.info("Initialise serial '%s' at speed '%d' ..." % (self.serial_port,self.serial_speed))
            self._link = serial.Serial( port=self.serial_port, baudrate=self.serial_speed,
                                        bytesize=__class__.DEFAULT_SERIAL_BITS,
                                        parity=__class__.DEFAULT_SERIAL_PARITY,
                                        stopbits=__class__.DEFAULT_SERIAL_STOP,
                                        timeout=__class__.DEFAULT_SERIAL_TIMEOUT,
                                        exclusive=True )
            # hardware reset of the radio module
            self.radioModuleHWreset()

            # on reset, RN2483 will send its firmware release
            # TODO: launch thread waiting for serial data
            _answer = str()
            _answer = self._link.read_until().decode("utf-8")   # serial timeout applies here
            if( len(_answer) ):
                log.debug("[init] recveived str: %s" % (_answer) )
                if( not ("rn2483" in _answer.lower()) ):
                    raise Exception("RN2483 module not found because answer was: " + str(_answer))
                self._fw_rev = [ int(x) for x in _answer.lower().split()[1].split('.') ]
            else:
                raise Exception("Lora module didn't answered!")

        except ValueError as ex:
            log.error("Firmware revision number are not integers: '%s'" % _answer.lower() + str(ex))
            raise ex
        except Exception as ex:
            log.error("while opening serial port '%s' with baudrate=%d " % (self.serial_port, self.serial_speed) + str(ex))
            raise ex
        log.debug("link '%s' @ '%d'bauds is validated as a serial port :)" % (self.serial_port,self.serial_speed) )

        # activate locking mechanism
        self._serial_lock= threading.Lock()


    def stop_serial(self):
        ''' release all resources allocated for RN2483 comm through serial link '''
        log.info("stop of serial link is on way ...")

        # stop threads

        # free resources

        # close serial link
        if( self._serial_lock ):
            self._serial_lock.acquire()
        if( self._link is not None and self._link.is_open is not False):
            self._link.close()
        self._link = None
        if( self._serial_lock ):
            self._serial_lock.release()
            del(self.serial_lock)
            self._serial_lock = None


    def _command(self, cmdIn, check=False):
        ''' send command to LoRa radio module '''
        result = str()
        with self._serial_lock:
            # first, flush input (recv) and output (send) buffer
            self._link.reset_input_buffer()
            self._link.reset_output_buffer()
            _cmd = cmdIn+'\r\n'
            self._link.write(_cmd.encode("utf-8"))
            #hexdump(_cmd.encode("utf-8"))
            result = self._link.read_until().decode("utf-8").rstrip('\r\n')
            if check and ( result is None or result != 'ok'):
                raise Exception("LoRa cmd '%s' responded with '%s'" % (cmdIn, result) )

        if( check ):
            log.debug("[LoRaCMD] '%s' returned '%s'" % (cmdIn,result) )
        else:
            log.debug("[LoRaCMD] '%s' executed" % (cmdIn) )
        return result


    def loraFactoryReset(self):
        ''' factory Reset of radio module
            return: RN2483's firmware release '''
        # [oct.18] maybe a bug but after a factory reset, answer to first command
        # is the firmware release ... so we ask it immediately to avoid further issues
        self._command("sys factoryRESET")
        time.sleep(2)
        return self._command("sys get ver")


    def radioModuleHWreset(self):
        ''' this will make use of the DTR line to force a hardware reset
            of the radio module.
            return: nothing '''
        if( self._gpio_rst is not None ):
            log.debug("[radioModule] HW reset through GPIO %d ..." % (self._gpio_rst))
            GPIO.setup(self._gpio_rst, GPIO.LOW)
            time.sleep(__class__.DEFAULT_SERIAL_TIMEOUT/2)      # just to get coherent with DTR reset
            GPIO.setup(self._gpio_rst, GPIO.HIGH)
            time.sleep(__class__.DEFAULT_SERIAL_TIMEOUT/2)

        elif( self._link is not None ):
            log.debug("[radioModule] HW reset through DTR line ...")
            # set polarity of DTR (RST line of RN2483)
            self._link.setDTR(True)  # activate RN2483's RST line
            self._link.reset_input_buffer()
            time.sleep(__class__.DEFAULT_SERIAL_TIMEOUT/2)
            self._link.setDTR(False) # release RN2483's RST line
            time.sleep(__class__.DEFAULT_SERIAL_TIMEOUT/2)


    def loraReset(self):
        ''' LoRa module software reset. stored internal configurations
            will be loaded automatically upon reboot. '''
        return self._command("sys reset", True)


    def loraSleep(self, val):
        ''' activate lora system sleep '''
        try:
            if( __class__.LORA_SYS_SLEEP[0] <= int(val) <= __class__.LORA_SYS_SLEEP[1] ):
                log.info("LoRa module will enter in sleep mode for %dms ..." % int(val) )
                self._command("sys sleep " + str(val)) # respond 'ok' after wakeup
                return
            log.warning("out of range sleep value '%s' !" % str(val))
        except Exception as ex:
            log.error("invalid sleep timeout (ms) '%s' !" % str(val))


    def loraMacPause(self):
        ''' pause LoRaWAN stack to enable RADIO modifications when a join has
            already been activated '''            
        log.warning("#WARNING: pausing LoRaWAN stack ...")
        self._command("mac pause")


    def loraMacResume(self):
        ''' resume the paused LoRaWAN stack '''
        self._command("mac resume", True)


    def loraMacSave(self):
        ''' save LoRaWAN parameters in NVM '''
        self._command("mac save")   # we don't check answer because it takes time to save to flash ...
                                    # mayeb longer than read timeout
        # wait until an answer
        res = self.receiveData( timeout=10000 )
        if( res is None or not res.startswith('ok') ):
            raise Exception("Failure to save mac!")
        log.debug("FLASH stored LoRa parameters :)")
        return True


    # LoRaWAN join
    def isConnected(self):
        ''' check if a connect (i.e join) ought to be undertaken ... '''
        _status = self.macStatus
        if( _status is None or not isinstance(_status,int) ):
            raise Exception("unable to obtain mac status ?!?!?!")

        print("[MAC] status = 0x%08X" % _status)
        # if network is joined and there's no need for a rejoin ... we're connected
        if( self._is_fwrev_ge('1.0.5') ):
            # Firmware rev >= 1.0.5
            if( ((_status >> 4) & 0b1)==1 ): return True
        else:
            # Firmware < 1.0.5
            if( (_status & 0b1)==1 and ((_status >> 15) & 0b1)==0 ): return True
        return False


    def connect(self, mode=None, **kwargs):
        ''' join either in OTAA or ABP mode '''

        # SF12 for join mode
        log.debug("[join] setting dr to 0 as default for join mode ...")
        self._command("mac set dr 0", True)
        self._command("radio set sf sf12", True)

        _res = None
        if( mode.lower() == 'otaa' ):
            _res = self._loraOTAAjoin( **kwargs )
        elif( mode.lower() == 'abp' ):
            _res = self._loraABPjoin( **kwargs )
        else:
            log.error("unknwon join mode '%s' ?!?!, ought to be one of %s" % (str(mode),str(__class__.LORA_JOIN_MODES)) )
            return False
        if _res is not True: return False

        # set channels status and data rates
        if( mode.lower() == 'abp' or self._command("mac get adr") == 'off' ):
            log.debug("\t... setting channels DataRates (DR) and status ..." )
            # set data rates (useless in OTAA with ADR enabled ?)
            # 0 --> SF12/125kHz
            # 1 --> SF11/125kHz
            # 2 --> SF10/125kHz
            # 3 --> SF9/125kHz
            # 4 --> SF8/125kHz
            # 5 --> SF7/125kHz
            self._command("mac set ch drrange 3 0 5", True)
            self._command("mac set ch drrange 4 0 5", True)
            self._command("mac set ch drrange 5 0 5", True)
            self._command("mac set ch drrange 6 0 5", True)
            self._command("mac set ch drrange 7 0 5", True)
            # enable channels (useless in OTAA with ADR enabled ?)
            self._command("mac set ch status 3 on", True)
            self._command("mac set ch status 4 on", True)
            self._command("mac set ch status 5 on", True)
            self._command("mac set ch status 6 on", True)
            self._command("mac set ch status 7 on", True)

        # set duty cycle
        log.debug("\t... setting duty-cycle to '%d' ..." % self._dcycle )
        for _ch in range(8):
            self._command("mac set ch dcycle %d %d" % (_ch,self._dcycle), True)

        # is there specified a DR for data exchange ?
        if self._data_rate is not None:
            log.info("set data_rate = '%d' for DATA exchanges ..." % self._data_rate)
            self._command("mac set dr %d" % self._data_rate, True)

        # is there specified a SF for data exchange ?
        if self._data_sf is not None and self._data_sf.lower() in __class__.LORA_SPREAD_FACTOR:
            log.info("set data_sf = '%s' for DATA exchanges ..." % self._data_sf.lower())
            self._command("radio set sf %s" % self._data_sf.lower(), True)

        # save config
        #self.loraMacSave()


    def _loraABPjoin(self, deveui=None, nwkskey=None, aapskey=None):
        ''' join with ABP protocol '''
        log.info("Start ABP join procedure ...")

        # ... configure additional bands
        log.debug("\t... adding channels and dutyCycles defs ...")
        self._command("mac set ch freq 3 867100000", True)
        self._command("mac set ch freq 4 867300000", True)
        self._command("mac set ch freq 5 867500000", True)
        self._command("mac set ch freq 6 867700000", True)
        self._command("mac set ch freq 7 867900000", True)

        # TODO!!
        raise NotImplementedError("ABP join not implemented")

        return False

    def _loraOTAAjoin(self, deveui=None, appeui=None, appkey=None):
        ''' join with OTAA protocol
            returns True, False or raise exception '''
        log.info("Start OTAA join procedure ...")
        if( deveui is not None): self.devEUI = deveui
        if( appeui is not None): self.appEUI = appeui
        if( appkey is not None): self.appKEY = appkey

        # try to join
        _retry = 5
        _sleep = 2
        while( self._shutdown_event.is_set() is not True and _retry > 0 ):
            _res = self._command("mac join otaa")   # check=false because we don't want an exception if answer differs from 'ok'
            print("(1) join res = %s" % _res)
            # check for acceptance of command
            if( _res != "ok" ):
                log.info("[join][devEUI=0x%s, appEUI=0x%s, appKEY=0x%s] command failed: '%s'" % (self.devEUI, self.appEUI, self.appKEY,_res))
                log.debug("... sleeping a bit before retrying join ...")
                time.sleep(_sleep); _sleep *= 2; _retry -= 1
                continue

            # ... and now wating for the join result
            print("(2) join ...")
            _res = self.receiveData(timeout=10000)      # wait up to ten seconds
            print("(3) join _res = %s" % str(_res))
            if( _res is None or _res.endswith('\r\n') is not True ):
                log.warning("# WARNING: partial retrieval from serial link !!")
                raise Eception("partial data from serial received :(")
            _res = _res.rstrip('\r\n')
            log.debug("\t received join answer: '%s'" % _res)
            if( _res == 'accepted' ):
                log.info("\t JOIN successful :)")
                return True

            log.info("[join][devEUI=0x%s, appEUI=0x%s, appKEY=0x%s] connection failed with code '%s'" % (self.devEUI, self.appEUI, self.appKEY,str(_res)))
            log.debug("... sleeping a bit before retrying join ...")
            time.sleep(_sleep); _sleep *= 2; _retry -= 1

        return False


    #
    # receiveData
    # Note: timeout in ms
    def receiveData(self, timeout=None):
        ''' try to read a line (i.e ends with \r\n) from serial link
            for a specific amount of time in ms (None means default timeout)
            Note: it is up to the caller to remove \r\n (if any) from buffer sent back '''
        if( self._link.is_open is not True ):
            raise Exception("serial port is not open, unable to read data!")

        with self._serial_lock:
            # save and apply new timeout
            if( timeout is not None ):
                _timeout = self._link.timeout   # copy
                self._link.timeout = float(timeout/1000)
                print("serial read timeout = %.2f" % float(self._link.timeout) )

            buf = self._link.read_until().decode("utf-8")

            # re-apply previously saved timeout
            if( timeout is not None ):
                self._link.timeout = _timeout   # restore previous value
     
        return buf if( len(buf)!=0 ) else None


    #
    # transmitData
    def transmitData(self, buf, port=1, ack=False):
        ''' transmit 'buf' data through an optional 'port'
            ack==False --> unconfirmed message, otherwise confirmed '''
        if( self._link.is_open is not True ):
            raise Exception("serial port is not open, unable to transfer data!")

        log.info("[TX_DATA] payload = '%s'" % str(buf) )

        # check input parameters
        if( not isinstance(port,int) or int(port) not in __class__.LORA_TX_PORTS_RNG ):
            raise Exception("either port '%s' is not an integer or not in range!" % str(port) ) 

        # prepare data to get sent
        out = ''.join(['%02x'%ord(c) for c in buf])
        _ackMode = "uncnf" if ack is False else "cnf"
        if( self._is_fwrev_ge('1.0.5') ):
            _res = self._command("mac tx %s %d %s" % (_ackMode, port, out))
        else:
            _res = self._command("mac tx %s %d %s" % (_ackMode, port, out) + '\r\n')
        if( _res != "ok" ):
            log.debug("## TX refused: '%s'" % _res )
            return False

        log.debug("TX msg has been accepted ... transmission will occur soon ...")
        return True


    #
    # PROPERTIES
    #

    # mac status (read-only)
    @property
    def macStatus(self):
        ''' read back mac status '''
        _status = None
        _retry  = 3
        while( _retry > 0 and self._shutdown_event.is_set() is not True ):
            _raw_status = self._command("mac get status")
            try:
                _status = int(_raw_status,16)
                break
            except ValueError as ex:
                log.debug("mac status '%s' is not a hex value!" % _raw_status)
                time.sleep(1)
                _retry-=1
                continue
        if( _status is None or not isinstance(_status,int) ):
            raise Exception("unable to obtain mac status ?!?!?!")
        return _status


    # HWEUI (read-only)
    @property
    def hwEUI(self):
        ''' read HW EUI writtent by microchip inside RN2483"s flash memory.
            This HWEUI can be used as the deveui. '''
        return self._command("sys get hweui")


    # end-device class
    @property
    def classDevice(self):
        ''' get end-device class '''
        if( self._is_fwrev_ge('1.0.5') ):
            # get end-device class (FW >= 1.0.5)
            return self._command("mac get class")
        else:
            log.debug("FW rev. is lower than '1.0.5'")
            return __class__.LORA_DEVICES_CLASSES[0]

    @classDevice.setter
    def classDevice(self, val):
        ''' set end-device class '''
        if( str(val)[0] not in __class__.LORA_DEVICES_CLASSES ):
            log.warning("invalid end-device class '%c', ought to be one of %s" % (str(val)[0],str(__class__.LORA_DEVICES_CLASSES)) )
            return
        if( self._is_fwrev_ge('1.0.5') ):
            self._command("mac set class " + str(val)[0], True)
        else:
            log.warning("device FW_rev '%s' is < to '1.0.5'" % str(self._fw_rev) )


    # DEVEUI
    @property
    def devEUI(self):
        ''' read devEUI attribute '''
        return self._command("mac get deveui")

    @devEUI.setter
    def devEUI(self, val):
        ''' set devEUI '''
        if( val is None ):
            log.warning("unsupported devEUI '%s'" % str(val) )
            return
        self._command("mac set deveui " + str(val), True )


    # APPEUI
    @property
    def appEUI(self):
        ''' read appEUI attribute '''
        return self._command("mac get appeui")

    @appEUI.setter
    def appEUI(self, val):
        ''' set appEUI '''
        if( val is None ):
            log.warning("unsupported appEUI '%s'" % str(val) )
            return
        self._command("mac set appeui " + str(val), True )


    # APPKEY
    @property
    def appKEY(self):
        return self._appKEY

    @appKEY.setter
    def appKEY(self, val):
        if( val is None ):
            log.warning("unsupported appKEY '%s'" % str(val) )
            return
        if( self._command("mac set appkey " + str(val), True ) == 'ok' ):
            self._appKEY = str(val)


    # MODULATION
    @property
    def modulation(self):
        ''' get radio modulation mode '''
        return self._command("radio get mod")

    @modulation.setter
    def modulation(self, val):
        ''' set modulation mode in ['lora','fsk'] '''
        if( val not in __class__.LORA_RADIO_MODULATION ):
            log.warning("invalid radio modulation '%s', ought to be one of %s" % (val,str(__class__.LORA_RADIO_MODULATION)) )
            return
        self._command("radio set mod " + val, True )


    # FREQ
    @property
    def freq(self):
        ''' get radio frequency '''
        return self._command("radio get freq")

    @freq.setter
    def freq(self, val):
        ''' set radio frequency '''
        try:
            for f in __class__.LORA_RADIO_FREQUENCIES:
                if( int(val) == int(f*1000000) ):
                    self._command("radio set freq " + str(val), True )
                    return
            log.warning("unknwon frequency '%s' ?!?!" % str(val) )
        except Exception as ex:
            log.error("error in frequency value '%s' ?!?!" % str(val) )
            raise ex


    # TX_POWER
    @property
    def pwr(self):
        ''' get TX power '''
        return self._command("radio get pwr")

    @pwr.setter
    def pwr(self, val):
        ''' set TX power '''
        try:
            if( int(val) not in __class__.LORA_RADIO_TX_POWER ):
                log.warning("invalid radio tx pwer provided")
                return
        except ValueError as ex:
            log.error("tx PWR '%s' ought to be an integer ... aborting" % (str(val)) )
            raise ex
        self._command("radio set pwr " + str(val), True)


    # SF (spreading factor)
    @property
    def sf(self):
        ''' get spreading factor '''
        return self._command("radio get sf")

    @sf.setter
    def sf(self, val):
        ''' set spreading factor '''
        if( val not in __class__.LORA_SPREAD_FACTOR ):
            log.warning("invalid spreading factor '%s', ought to be one of %s" % (val,str(__class__.LORA_SPREAD_FACTOR)) )
            return
        self._command("radio set sf " + val, True )


    # CRC
    @property
    def crc(self):
        ''' get radio crc mode '''
        return self._command("radio get crc")

    @crc.setter
    def crc(self, val):
        ''' set crc parameter in ['on','off'] '''
        if( val not in __class__.LORA_ON_OFF ):
            log.warning("invalid CRC parameter '%s', ought to be one of %s" % (val,str(__class__.LORA_ON_OFF)) )
            return
        self._command("radio set crc " + val, True )


    # Invert IQ (iqi)
    @property
    def iqi(self):
        ''' get radio iqi '''
        return self._command("radio get iqi")

    @iqi.setter
    def iqi(self, val):
        ''' set iqi parameter in ['on','off'] '''
        if( val not in __class__.LORA_ON_OFF ):
            log.warning("invalid invert IQ parameter '%s', ought to be one of %s" % (val,str(__class__.LORA_ON_OFF)) )
            return
        self._command("radio set iqi " + val, True )


    # CR (coding rate)
    @property
    def cr(self):
        ''' get coding rate factor '''
        return self._command("radio get cr")

    @cr.setter
    def cr(self, val):
        ''' set coding rate '''
        if( val not in __class__.LORA_CODING_RATE ):
            log.warning("invalid coding rate '%s', ought to be one of %s" % (val,str(__class__.LORA_CODING_RATE)) )
            return
        self._command("radio set cr " + val, True )


    # BW (bandwidth)
    @property
    def bw(self):
        ''' get current bandwidth '''
        return self._command("radio get bw")

    @bw.setter
    def bw(self, val):
        ''' set bandwidth '''
        try:
            for _bw in __class__.LORA_BANDWIDTH:
                if( int(val) == _bw ):
                    self._command("radio set bw " + str(val), True )
                    return
            log.warning("unknwon bandwidth '%s', ought to be one of %s" % (str(val),str(__class__.LORA_BANDWIDTH)) )
        except Exception as ex:
            log.error("error in bandwidth value '%s' ?!?!" % str(val) )
            raise ex


    # WDT (rx watchdog)
    @property
    def wdt(self):
        ''' get rx watchdog '''
        return self._command("radio get wdt")

    @wdt.setter
    def wdt(self, val):
        ''' set rx watchdog '''
        try:
            if( 0 <= int(val) <= __class__.LORA_RX_WATCHDOG ):
                self._command("radio set wdt " + str(val), True )
                return
            log.warning("out of limits rx watchdof '%s' ?!?!" % str(val) )
        except Exception as ex:
            log.error("error in watchdog timeout value '%s' ?!?!" % str(val) )
            raise ex


    # Battery level
    @property
    def batlvl(self):
        ''' get current battery-level '''
        return self._batlvl if self._batlvl is not None else __class__.LORA_BAT_LVL_RNG[-1]

    @batlvl.setter
    def batlvl(self, val):
        ''' set battery-level '''
        if( val is None ):
            self._batlvl = None
            return
        try:
            if( int(val) in __class__.LORA_BAT_LVL_RNG ):
                _res = self._command("mac set bat %d" % val, True )
                if( _res is None or _res != 'ok'):
                    raise Exception("error while setting battery level!")
                return
            log.warning("out-of-range battery-level '%s'" % str(val) )
        except Exception as ex:
            log.error("error in battery-level value '%s' ?!?!" % str(val) )
            raise ex


