#!/bin/bash
#

# exit on first error
set -e

#
# Variables definitions
MQTT_APP="/usr/sbin/mosquitto"
MQTT_DIR="/mqtt"
MQTT_CONFIG_DIR="${MQTT_DIR}/config"
MQTT_CONFIG_ADDON_DIR="${MQTT_CONFIG_DIR}/conf.d"
MQTT_LOGDIR="${MQTT_DIR}/log"
MQTT_LOGFILE="${MQTT_LOGDIR}/mosquitto.log"
MQTT_DEBUG=${MQTT_DEBUG:-0}


echo -e "\n============ MQTT ${MQTT_VER} ======================================================="

#
# arguments analysis
_command=0
[ $# -eq 0 ] && { echo -e "\n###ERROR: no arguments ?!?!" >&2; return 1; }
if [ "${1:0:1}" = '-' ]; then
    # First argument is an option (either from [CMD] or command line)
    set -- ${MQTT_APP} "$@"
else
    # First argument is a command ... thus we ought to launch it!
    _command=1
    set -- "$@"
fi


#
# Regular launch of docker ?
if [ ${_command} -eq 0 ]; then
    # Regular run

    # Mosquitto user / group ?
    [ "X${MOSQUITTO_UID}" = "X" -o "X${MOSQUITTO_GID}" = "X" ] && { echo -e "\n###ERROR: unspecfied mosquitto UID/GID, aborting docker launch!" >&2; exit 1; }
    echo -e "=== mosquitto user UID=${MOSQUITTO_UID}, GID=${MOSQUITTO_GID}"
    [ $(id -g mosquitto >& /dev/null; echo $?) -ne 0 ] && { groupadd --gid ${MOSQUITTO_GID} mosquitto; }
    [ $(id -u mosquitto >& /dev/null; echo $?) -ne 0 ] && { useradd --uid ${MOSQUITTO_UID} --gid ${MOSQUITTO_GID} -M mosquitto; }
#   chown -R mosquitto:mosquitto ${MQTT_DIR}

    # SSL enablers ?
    if [ -f ${MQTT_CONFIG_DIR}/cert.pem -a -f ${MQTT_CONFIG_DIR}/chain.pem -a -f ${MQTT_CONFIG_DIR}/privkey.pem ]; then
        echo -e "=== [ENABLED] MQTT+SSL support enabled :)"
#       [Sep.17] no need to copy SSL files as they are all 'mounted' in /mqtt/conf/
#       cp ${MQTT_DIR}/{cert,chain,privkey}.pem ${MQTT_CONFIG_DIR}
#       chown -R mosquitto:mosquitto ${MQTT_CONFIG_DIR}
    else
        echo -e "=== [DISABLED] no MQTT+SSL support :|"
        mv ${MQTT_CONFIG_ADDON_DIR}/ssl.conf ${MQTT_CONFIG_ADDON_DIR}/ssl.conf.disabled
    fi

    # Debug mode ?
    if [ "X${MQTT_DEBUG}" = "X1" ]; then
        echo -e "=== [ENABLED] debug mode activated"
        for f in $(ls ${MQTT_CONFIG_DIR}/*.conf); do
            sed -i '/^connection_messages */s/ $/true/' $f
            sed -i '/#log_type/s/^.//' $f
            sed -i '/^auth_opt_log/s/^/#/' $f
        done
    fi

    # logs
    touch ${MQTT_LOGFILE}
    chown -R mosquitto:mosquitto ${MQTT_LOGDIR}
fi

#
# [oct.18] copy auth plugin if newer
if [ -f /root/mosquitto-auth-plug/auth-plug.so ]; then
    echo -e "=== copying auth-plug.so to '${MQTT_CONFIG_DIR}' ..."
    cp -af /root/mosquitto-auth-plug/auth-plug.so ${MQTT_CONFIG_DIR} 2>/dev/null
    chmod a+rx ${MQTT_CONFIG_DIR}/auth-plug.so
fi

#
# Launch app
echo -e "=== Environment variables ..."
env
echo -e "=== Launching app '$@' ..."
exec "$@"


#
# END

