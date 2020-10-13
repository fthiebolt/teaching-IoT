#
# mqttOCampus
#
# Fedora latest based docker file
#
# Thiebolt F.   oct.20  if switching to mosquitto-1.6.12, you need
#                       mosquitto-auth-plugin from https://github.com/sevg1/mosquitto-auth-plug
# Thiebolt F.   oct.18  switch to new 1.5.3
# Thiebolt F.   sep.17  initial release
#

# Fedora 32 at the time of writing
FROM fedora:latest
MAINTAINER "Francois <thiebolt@irit.fr>"

# Build ARGS
#ARG APP="/app"

# Switch to bash as default shell
SHELL [ "/bin/bash", "-c" ]

# Location of files to add to the container
# Note this <relative_path> to the build env @ host
# [oct.18] auth_plugin releases are too old --> git
ENV DOCKYARD="/dockyard" \
    DESTDIR="/mqtt" \
    MQTT_VER="1.6.12"
    # AUTH_PLUGIN_VER="0.1.2"

# Switch to root user to enable installation (default)
#USER root

# Copy configuration directory
COPY ${DOCKYARD} /${DOCKYARD}

# Copy application directory
COPY ${APP} ${DESTDIR}

# passwd generated with 'openssl passwd' on CentOS 7.7

#
# Set-up ssh environnement / password / authorized-key + file copy
RUN echo -e "Starting setup ..." \
    # root passwd
    && echo 'root:JfNZIhkvEchfM' | chpasswd -e \
    # SSH authorized keys
    && cp -af ${DOCKYARD}/root / \
    && mkdir -p /root/.ssh \
    && cp -af ${DOCKYARD}/authorized_keys /root/.ssh/ \
    && chmod 600 /root/.ssh/authorized_keys \
    && chmod g-w /root \
    # custom motd message
    && cp -af ${DOCKYARD}/myMotd /etc/motd.d/ \
    && chmod 644 /etc/motd.d/myMotd \
    # Supervisor setup
    && cp -af ${DOCKYARD}/supervisord.d /etc \
    # MQTT config and log files
    && mkdir -p ${DESTDIR}/config ${DESTDIR}/log \
    && cp -af /${DOCKYARD}/mosquitto/* ${DESTDIR}/config \
    # system stuff
    && dnf -y --nogpgcheck install \
        git \
        procps \
        bind-utils \
        findutils \
        supervisor \
        openssh-clients \
        openssh-server \
        python3-pip \
        libuuid-devel \
        libwebsockets-devel \
        wget \
        curl-devel \
        openssl-devel openssl-static \
        make gcc gcc-c++ \
        postgresql-devel \
#   && dnf -y --nogpgcheck --allowerasing upgrade \
    && dnf -y --nogpgcheck install vim \
    && dnf clean all \
    # Supervisor setup
    && cp -af /${DOCKYARD}/supervisord.d /etc \
    # [oct.20] fix for 'unable to hopen HTTP server'
    && mkdir -p /run/supervisor \
    # SSH server setup
    && mkdir -p /var/run/sshd \
    && ssh-keygen -A \
    # Mosquitto
    # note: we install package only for mosquitto user creation
    && dnf -y install mosquitto \
    && cd /root \
    && wget http://mosquitto.org/files/source/mosquitto-${MQTT_VER}.tar.gz \
    && tar -z -xvf mosquitto-${MQTT_VER}.tar.gz \
    && ln -s mosquitto-${MQTT_VER} mosquitto \
    && cd /root/mosquitto \
    && sed -i '/^WITH_WEBSOCKETS/s/:=.*/:=yes/g' config.mk \
    && sed -i '/^WITH_SRV/s/:=.*/:=no/g' config.mk \
    && sed -i '/^WITH_DOC/s/:=.*/:=no/g' config.mk \
    && sed -i '/^prefix=/s/=.*/=\/usr/g' config.mk \
    # && echo "LIB_SUFFIX=64" >> config.mk \
    # patch to mosquitto-1.4.11
    # && cp -af src/mosquitto.c src/mosquitto.c.orig && sed -i '/define *_BSD_SOURCE/s/^/\/\//' src/mosquitto.c \
    && DESTDIR="" make prefix=/usr -j all install \
    # Mosquitto auth plugin
    && cd /root \
#   && git clone https://github.com/jpmens/mosquitto-auth-plug.git \
    && git clone https://github.com/sevg1/mosquitto-auth-plug.git \
#   && wget https://github.com/jpmens/mosquitto-auth-plug/archive/${AUTH_PLUGIN_VER}.tar.gz \
#   && tar -z -xvf ${AUTH_PLUGIN_VER}.tar.gz \
#   && ln -s mosquitto-auth-plug-${AUTH_PLUGIN_VER} mosquitto-auth-plug \
    && cd /root/mosquitto-auth-plug \
    && cp -af config.mk.in config.mk \
    && sed -i '/^BACKEND/s/yes/no/' config.mk \
    && sed -i '/^BACKEND_HTTP/s/no/yes/' config.mk \
    && sed -i '/^BACKEND_POSTGRES/s/no/yes/' config.mk \
    && sed -i '/^MOSQUITTO_SRC/s/=.*/= \/root\/mosquitto/' config.mk \
    && make \
    && cp -af np /mqtt \
    && cp -af auth-plug.so /mqtt/config \
    && chmod -R a+rx /mqtt
    # app. specific requirements
    # && pip3 install -r ${DOCKYARD}/requirements.txt


# Volumes (useful ??)
#VOLUME [ "/mqtt" ]

# Exposed ports
# 1883: MQTT
# 8883: MQTT+SSL/TLS
# 9001: MQTT websockets
# 9883: MQTT websockets+SSL/TLS
# 22  : SSH daemon
EXPOSE 22 1883 9001
#EXPOSE 22 1883 8883 9001 9883

# ENTRYPOINT & CMD
#ENTRYPOINT [ "/entrypoint.sh" ]
#CMD [ "-c", "/mqtt/config/neocampus.conf" ]

# CMD
CMD ["/usr/bin/supervisord", "-n" ]

