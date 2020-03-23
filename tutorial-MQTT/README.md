# dataCOllector | MQTT tutorial #
________________________________

This directory holds q MQTT sample app. used to collect data from the neOCampus MQTT broker and to write them
down to a mongoDB database (commented)-out).

  - **settings.py** is the main configuration file. You should replace constants according to your environment
  - **datacollector.py** the main app.

### Environment variables ###
When you start this application (see below), you can pass several environment variables:

  - **DEBUG=1** this is our application debug feature
  - **MQTT_SERVER** and **MQTT_PORT**
  - **MQTT_USER** and **MQTT_PASSWD** are MQTT credentials
  - **MQTT_TOPICS** json formated list of topics to subscribe to
  - **MQTT_UNITID** is a neOCampus identifier for msg filtering
  - **MONGO_USER** and **MONGO_PASSWD** are MongoDB credentials
  - **MONGO_HOST** and **MONGO_PORT**
  - **MONGO_DATABASE**   name of the database


### start application ###
```
DEBUG=1 MQTT_PASSWD='passwd' MONGO_PASSWD='passwd' python3 dataCOllector.py
```  

