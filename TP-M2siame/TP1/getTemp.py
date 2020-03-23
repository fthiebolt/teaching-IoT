#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Threaded CPU temperature retrieval app.
#
# usage: ./getTemp.py -d
#
# Thiebolt  aug.19  added do_every
# Thiebolt  aug.17  initial release
#



# #############################################################################
#
# Import zone
#
import os
import sys
import errno
import signal
import time
import argparse
import glob

from time import localtime, strftime

import logging

import threading



# #############################################################################
#
# Global variables
#
# Variable to store commandline arguments
ARGS                = None

# Path to look for temp*_input files
_base_pattern       = "/sys/devices/platform/coretemp.*/hwmon/hwmon*/temp*_input"
temp_files          = None


# thread related vars
timer               = None


# general purpose variables
log         = None
_shutdown   = False



# #############################################################################
#
# Functions
#


#
# Function ctrlc_handler
def ctrlc_handler( signum, frame ):
    global _shutdown
    print("<CTRL + C> action detected ...");
    _shutdown = True
    # Stop monitoring
    stopMonitoring()


#
# Function stopping the monitoring
def stopMonitoring():
   global timer
   print("[Shutdown] stop timer operations ...");
   timer.cancel()
   timer.join()
   del timer


#
# threading.timer helper function
def do_every( interval, worker_func, iterations = 0, *args, **kwargs):
    global timer
    # launch new timer
    if( iterations != 1):
        timer = threading.Timer (
                       interval,
                       do_every, [interval, worker_func, 0 if iterations == 0 else iterations-1], kwargs );
        timer.start()
    
    # launch worker function
    worker_func( **kwargs);


#
# Function to display temperature from files
def display_temp( temp_files, *args, **kwargs):
    log.debug("Files to watch:\n" + str(temp_files) )
    for _file in temp_files:
        with ________________:
            print(___________________________________________,end=None )



# #############################################################################
#
# Main
#
def main():
    ''' comment related to the function '''

    # Global variables
    global ARGS, log, timer, temp_files, _shutdown

    # --- 1. Find temperature files
    if( temp_files is None):
        log.info("Looking for temperature files in '%s'" % (_base_pattern) )
        temp_files = glob.glob(_base_pattern, recursive=True)
        log.debug("Found these files :\n" + str(temp_files) )


    # --- 2. Launch thread
    log.info("Launching timer with '%d' seconds interval ..." % (ARGS.frequency) )
    try:
        _params = dict()
        _params['temp_files'] = temp_files
        do_every( ARGS.frequency, display_temp, **_params );
    except Exception as ex:
        log.error("Error while starting timer: " + str(ex))
        sys.exit(1)


    # --- 3. Wait for shutdown
    log.info("Waiting from timer to finish ...");
    while( _shutdown is not True):
        time.sleep(1)

    '''
    if( timer is not None ):
        del timer
    try:
        _params = dict()
        _params['temp_files'] = temp_files
        timer = threading.Timer( ARGS.frequency, display_temp, kwargs=_params )
        timer.start()
    except Exception as ex:
        log.error("Error while starting timer: " + str(ex))
        sys.exit(1)


    # --- 3. Wait for shutdown
    log.info("Main thread waiting for completion ...")
    while( _shutdown is not True):
        time.sleep(1)
    '''

    # --- 4. termination
    log.info("\n\t[end] Byebye")
    sys.exit(0);



# ---- Define 'main' function as the entry point for this script -------------
# ---- Note: on an 'import' of this module, the '__main__' function is not executed
if __name__ == '__main__':

    #
    print("\n###\n[M2siame] CPU temp. retrieval demo")
    print("###")

    # Trap CTRL+C (kill -2)
    signal.signal( signal.SIGINT, ctrlc_handler )

    # Parse arguments
    parser = argparse.ArgumentParser(
                         description="CPU temperature retrieval app. \
                         \n Press <CTRL> + C to terminate the program." )

    parser.add_argument( '-f', '--frequency', type=int,
                         default=10,
                         help="Recurrent interval to call the function." )

    # debug mode
    parser.add_argument( '-d', '--debug', action="store_true",
                         help="Debug mode (False as default)." )

    ARGS = parser.parse_args()


    # Logging setup
    logging.basicConfig(format="[%(asctime)s][%(module)s:%(funcName)s:%(lineno)d][%(levelname)s] %(message)s", stream=sys.stdout)
    log = logging.getLogger()

    if( ARGS.debug is True ):
        print("\n[DBG] DEBUG mode activated ... ") 
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)

    # general information
    log.debug("\nParsed CLI arguments = " + str(ARGS) )
    log.info("Start CPU temp. monitoring app. with freq='%d'seconds" % (ARGS.frequency) )

    # call main function
    main()


# The END - Jim Morrison 1943 - 1971

