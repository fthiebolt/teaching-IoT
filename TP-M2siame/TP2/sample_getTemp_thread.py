#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Threading timer sample code applied to RPi CPU's temp. reading
#
# Thiebolt  aug.19  added support to rpi_utils module
# Francois  Apr.16  initial release
#



# #############################################################################
#
# Import zone
#
import errno
import os
import signal
import syslog
import sys

import time

import threading
import json

''' to remember
# To extend python librayrt search path
_path2add='./libutils'
if (os.path.exists(_path2add) and not os.path.abspath(_path2add) in sys.path):
    sys.path.append(os.path.abspath(_path2add))
# Raspberry Pi related imports
from rpi_utils import *
'''
from libutils.rpi_utils import getCPUtemperature



# #############################################################################
#
# Global Variables
#

# Measurement related
# seconds between each measure.
measure_interleave = 5

timer = None
__shutdown = False



# #############################################################################
#
# Functions
#



#
# Function ctrlc_handler
def ctrlc_handler(signum, frame):
    global __shutdown
    print("<CTRL + C> action detected ...");
    __shutdown = True
    # Stop monitoring
    stopMonitoring()

#
# Function stoping the monitoring
def stopMonitoring():
    global timer
    print("[Shutdown] stop timer operations ...");
    timer.cancel()
    timer.join()
    del timer


#
# threading.timer helper function
def do_every (interval, worker_func, iterations = 0):
#   global __shutdown
    global timer
#   if __shutdown: return;
    # launch new timer
    if ( iterations != 1):
        timer = threading.Timer (
                        interval,
                        do_every, [interval, worker_func, 0 if iterations == 0 else iterations-1] );
        timer.start()
    # launch worker function
#   if not __shutdown:
    worker_func();



# --- neOCampus related functions ---------------------------------------------
# Acquire sensors and publish
def getSensors():
    # get CPU temperature (string)
    CPU_temp = getCPUtemperature()
    print(time.strftime("%H:%M:%S") + " RPi temperature = " + CPU_temp)


# #############################################################################
#
# MAIN
#

def main():

    # Global variables
    global timer

    # Trap CTRL+C (kill -2)
    signal.signal(signal.SIGINT, ctrlc_handler)

    # Launch Acquisition & publish sensors till shutdown
    do_every(measure_interleave, getSensors);

    # waiting for all threads to finish
    print("Waiting from timer to finish ...");
    timer.join()


# Execution or import
if __name__ == "__main__":

    # Start executing
    main()


# The END - Jim Morrison 1943 - 1971
#sys.exit(0)

