#!/home/pi/1TEMP/.venv/bin/python3

from time import sleep, perf_counter
import board, logging
import adafruit_dht
from gpiozero import LED
import paho.mqtt.client as mqtt  # used for mqtt
import sys, socket, os, json     # Used for mqtt
from pathlib import Path         # Used for mqtt
from subprocess import check_output # alternate method to see IP address

#====== IP ADDRESS CHECK ==============#
# Getting IP address. IP address will change over time and if Pi is offline vs online. 

def get_ipGP():
    ip = "not connected"
    routes = json.loads(os.popen("ip -j -4 route").read())
    for r in routes:
        if r.get("dev") == "wlan0" and r.get("prefsrc"):
            ip = r['prefsrc']
            continue
    return ip

def check_connection():
    sleep(3) # allow time for device to connect
    logging.info(check_output(['hostname', '-I'])) # Alternate way to display IP for confirmation
    hostname = socket.gethostname()
    ip3 = get_ipGP()  # Method by GPayne
    if ip3 == 'not connected':
        connected = False
    else:
        connected = True
    return connected, hostname, ip3

#====== MQTT CALLBACK FUNCTIONS ==========#
# Each callback function needs to be 1) defined and 2) assigned/linked in main program below
# on_connect = Connect to the broker and subscribe to TOPICs
# on_disconnect = Stop the loop and log the reason code
# on_message = When a message is received get the contents and assign it to a python dictionary (must be subscribed to the TOPIC)
# on_publish = Send a message to the broker

def on_connect(client, userdata, flags, rc):
    """ on connect callback verifies a connection established and subscribe to TOPICs"""
    logging.info("attempting on_connect")
    if rc==0:
        mqtt_client.connected = True          # If rc = 0 then successful connection
        client.subscribe(MQTT_SUB_TOPIC)     # Subscribe to topic
        logging.info("Successful Connection: {0}".format(str(rc)))
        logging.info("Subscribed to: {0}\n".format(MQTT_SUB_TOPIC))
    else:
        mqtt_client.failed_connection = True  # If rc != 0 then failed to connect. Set flag to stop mqtt loop
        logging.info("Unsuccessful Connection - Code {0}".format(str(rc)))

    ''' Code descriptions
        0: Successful Connection
        1: Connection refused: Unacceptable protocol version
        2: Connection refused: Identifier rejected
        3: Connection refused: Server unavailable
        4: Connection refused: Bad user name or password
        5: Connection refused: Not authorized '''

def on_message(client, userdata, msg):
    """on message callback will receive messages from the server/broker. Must be subscribed to the topic in on_connect"""
    global mqtt_newmsg, incomingD
    if msg.topic == MQTT_SUB_TOPIC:
        incomingD = json.loads(str(msg.payload.decode("utf-8", "ignore")))  # decode the json msg and convert to python dictionary
        mqtt_newmsg = True
        # Debugging. Will print the JSON incoming payload and unpack the converted dictionary
        logging.debug("Receive: msg on subscribed topic: {0} with payload: {1}".format(msg.topic, str(msg.payload))) 
        logging.debug("on_message converted (JSON->Dictionary) and unpacking")
        for key, value in incomingD.items():
            logging.debug("on_message Dict key:{0} value:{1}\n".format(key, value))

def on_publish(client, userdata, mid):
    """on publish will send data to broker"""
    logging.debug("msg ID: " + str(mid)) 
    pass 

def on_disconnect(client, userdata,rc=0):
    logging.debug("DisConnected result code "+str(rc))
    mqtt_client.loop_stop()

def get_login_info(file):
    home = str(Path.home())                    # Import mqtt and wifi info. Remove if hard coding in python script
    with open(os.path.join(home, file),"r") as f:
        user_info = f.read().splitlines()
    return user_info

def main():
    ''' define global variables '''
    global mqtt_client, outgoingD, incomingD, mqtt_newmsg
    global MQTT_SUB_TOPIC, MQTT_PUB_DATA_TOPIC, MQTT_PUB_RPI_TOPIC           # Can add more topics for subscribing/publishing
    global led

    #==== LOGGING/DEBUGGING ============#
    # Logging package allows you to easiliy turn print-like statements on/off GLOBALLY with 'level' settings below
    # Using basicConfig logging at root level. The 'level', on/off, controls other modules with logging enabled.
    
    logging.basicConfig(level=logging.DEBUG)  # Set to DEBUG to get variables and status messages. 
                                              # Set to INFO for status messages only.
                                              # Set to CRITICAL to turn off

    #==== HARDWARE SETUP ===============# 
    led1 = LED(27)
    freezer1DHT = adafruit_dht.DHT22(board.D18, use_pulseio=False) # pulseio false for RPi

    #====   SETUP MQTT =================#
    # Check for wifi connection. Using hostname for MQTT_SERVER so IP address is not necessary but can be useful.
    connected, hostname, ip_address= check_connection()
    if connected:
        logging.info("Connected first time")
    else:
        logging.info("Not connected first time")
        logging.info("Waiting and then checking connection 2nd time")
        sleep(3)
        connected, hostname, ip_address= check_connection()
        if connected:
            logging.info("2nd check successful")
        else:
            logging.info("2nd check failed. Either offline or problems connecting.")
    logging.info("IP address: {0}".format(ip_address))
    logging.info("Hostname: {0}".format(hostname))

    user_info = get_login_info("cred")
    MQTT_SERVER = 'raspberrypi.local'            # Replace with IP address of device running mqtt server/broker
    MQTT_USER = user_info[0]                     # Replace with your mqtt user ID
    MQTT_PASSWORD = user_info[1]                 # Replace with your mqtt password
    MQTT_SUB_TOPIC = 'trailer/pi/instructions'   # Subscribe topic (incoming messages, instructions)
    MQTT_PUB_DATA_TOPIC = 'trailer/freezer1/data'     # Publish topic (outgoing messages, data, instructions)
    MQTT_PUB_RPI_TOPIC = 'trailer/rpi/connection'     # Publish topic (outgoing messages, data, instructions)
    MQTT_CLIENT_ID = 'pi3B'                      # Give your device a name
    WIFI_SSID = user_info[2]                     # Replace with your wifi SSID
    WIFI_PASSWORD = user_info[3]                 # Replace with your wifi password

    #==== START/BIND MQTT FUNCTIONS ====#
    # Create a couple flags in the mqtt.Client class to handle a failed attempt at connecting. If user/password is wrong we want to stop the loop.
    mqtt.Client.connected = False          # Flag for initial connection
    mqtt.Client.failed_connection = False  # Flag for failed initial connection
    # Create our mqtt_client object and bind/link to our callback functions
    mqtt_client = mqtt.Client(MQTT_CLIENT_ID)             # Create mqtt_client object
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASSWORD) # Need user/password to connect to broker
    mqtt_client.on_connect = on_connect                   # Bind on connect
    mqtt_client.on_disconnect = on_disconnect             # Bind on disconnect
    mqtt_client.on_message = on_message                   # Bind on message
    mqtt_client.on_publish = on_publish                   # Bind on publish
    logging.info("Connecting to: {0}".format(MQTT_SERVER))
    mqtt_client.connect(MQTT_SERVER, 1883) # Connect to mqtt broker. This is a blocking function. Script will stop while connecting.
    mqtt_client.loop_start()               # Start monitoring loop as asynchronous. Starts a new thread and will process incoming/outgoing messages.
    # Monitor if we're in process of connecting or if the connection failed
    while not mqtt_client.connected and not mqtt_client.failed_connection:
        logging.info("Waiting")
        sleep(1)
    if mqtt_client.failed_connection:      # If connection failed then stop the loop and main program. Use the rc code to trouble shoot
        mqtt_client.loop_stop()
        sys.exit()

    #==== MAIN LOOP ====================#
    # MQTT setup is successful. Initialize dictionaries and start the main loop.
    led1.on()
    outgoingD, incomingD = {}, {}
    outgoingD['data'] = {}
    outgoingD['ipAddr'] = check_connection()
    mqtt_client.publish(MQTT_PUB_RPI_TOPIC, json.dumps(outgoingD['ipAddr']))  # publish IP address info
    mqtt_newmsg = False
    t0_sec = perf_counter()
    msginterval = 3.0  # Adjust for how often data should be collected. DHT11 min is 2sec
    
    try:
        while True:
            if (perf_counter() - t0_sec) > msginterval:
                t0_sec = perf_counter()
                try:
                    temperature_c = freezer1DHT.temperature
                    temperature_f = temperature_c * (9 / 5) + 32
                    humidity = freezer1DHT.humidity
                    outgoingD['data']['tempFf'] = float(temperature_f)
                    outgoingD['data']['humidityi'] = int(humidity)
                    mqtt_client.publish(MQTT_PUB_DATA_TOPIC, json.dumps(outgoingD['data']))  # publish data
                    logging.debug(
                        "Temp: {:.1f} F / {:.1f} C    Humidity: {}% ".format(
                            temperature_f, temperature_c, humidity
                        )
                    )
                except RuntimeError as error:
                    logging.info(error.args[0])
                    continue
                #except Exception as error:  # Commenting out to see if it will retry on error
                #    freezer1DHT.exit()
                #    raise error
    except KeyboardInterrupt:
        logging.info("Pressed ctrl-C")
    finally:
        logging.info("GPIO cleaned up automatically with gpiozero")

if __name__ == "__main__":     # Will run main() code when program is executed as a script (vs imported as a module)
    main()