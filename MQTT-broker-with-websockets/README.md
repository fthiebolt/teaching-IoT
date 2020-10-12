# mqttOCampus: Dockerized **MQTT** broker #
___________________________________________________________


We provides a container with a MQTT broker featuring:  
  - MQTT 3.1.1 protocol (port 1883)  
  - SSL support (port 8883)  
  - Websockets support (port 9001)  
  - Websockets support + SSL (port 9003)  
  - bridge support (virtual broker)  
  - mosquitto_auth plugin (Postgres, HTTP)
  - ssh daemon support (add your public key to 'dockyard/authorized_keys' before image generation

**Note [oct.20]**: this version does not provides SSL support because it both requires a valid certificate that ough to get send to mqtt though mount points ... that's the reason 'entrypoint.sh' exists  
  
## MQTT@neOCampus: configuration ##
MQTT broker setup is included in ```neocampus.conf```

### start container ###
```
docker-compose up -d
[alternative] specifying a specific MQTT config file (that OUGHT to exist of course)
MQTT_CONFIG_FILE=m2siame.conf docker-compose up -d
```  

### fast update of existing running container ###
```
docker-compose up --build -d
```  

### ONLY (re)generate image of container ###
```
docker-compose --verbose build --force-rm --no-cache
[alternative] docker build --no-cache -t mqttocampus -f Dockerfile .
```

### start container for maintenance ###
```
docker run -v /etc/localtime:/etc/localtime:ro -v "$(pwd)"/app:/opt/app:rw -it mqttocampus bash
```

### ssh root @ container ? ###
Yeah, sure like with any VM (see docker-compose.yml for port confirmation):
```
ssh -p 2220 root@locahost
```

___________________________________________________________

### OLD'n DEPRECATED stuffs ###
**[Sep.17]** MQTT broker now check for `clientID` containing special chars like + or # or /  
We set a special version 'mqttocampus:dev' whose such extra ACL check is disabled.

