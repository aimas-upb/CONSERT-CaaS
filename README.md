# CONSERT-CaaS
Implementation of search and discovery capabilities for sensor and actuator context information.

## General Info
Provides implementation and deployment of web-enabled RESTful protocol for mananging, discovering and searching for smart Web Things. The examples provided are based on the capabilities of lab PR308.

## Technologies
- Python 3.6
- Based on Mozilla [webthing] (https://github.com/mozilla-iot/webthing-python) implementation
- Required Python packages are provided as `requirements.txt` file  in `CONSERT-CaaS` directory
- Running a SensorNode server, also requires an instance of a [rosbridge server] (https://wiki.ros.org/rosbridge_server)

## Installation
- Download source code and examples, available at `https://github.com/ami-lab/CONSERT-CaaS`
- Set up a new Python environment and install required packages

To install requirements:

	$ pip install -r requirements.txt

- In `CONSERT-CaaS/manager_node` directory make sure you change `sensornode_config.yaml` and `managernode_config.yaml` as you need.


## Launch
#### ManagerNode server
	$ python managernode.py

#### SensorNode
SensorNode will try to join at ManagerNode server. If ManagerNode is not running, SensorNode will run anyway, but restart is needed to join at the ManagerNode

	$ python sensornode.py

#### SensorNode test mode
If you run the SensorNode server without ROS availability services, add `test_mode` command line argument. This will change the availability of managed WebThings with a random value (True or False) every 10 seconds.

	$ python sensornode.py test_mode

## Example of use
#### SensorNode
To check if SensorNode is working properly, you can try to get a description of the things it is responsible for. This is done by sending a GET request to the base URL:

	import requests
	import json

	# send a GET request to base URL of the SensorNode
	r = requests.get('http://localhost:8888', params={'format':'json-ld'})

	# use json.loads() method to get a python dict from the response string
	response_message = json.loads(r.content.decode('ascii'))

	# use json.dumps() method to print the json with spacing, so it is easier to read 
	print(json.dumps(response_message, indent=4))

#### ManagerNode
Before you can have a look at the description of the ManagerNode, you have to join by sending a POST request. This way, you get a key to authenticate. The rest of the process is almost the same as with the SensorNode. 
Note that the URL of the join and other capabilities of the ManagerNode have the form of `<base_url>/coord/location/<name_of_the_context_domain>/<capability>`

	import requests
	import json

	# send a POST request to join the manager, use 'as=client' param to get a key
	r = requests.post('http://localhost:7777/coord/location/lab308/join', params={'as': 'client'})

	# use json.loads() method to get a python dict from the response string
	response_message = json.loads(r.content.decode('ascii'))

	# if ManagerNode is running as expected, you should get a json as response, with 'client_id' as a key
	# The response_message should look like {'client-id': 'c0cc4841-e7a0-4fb4-9444-e7e55581e291'}
	print(response_message)

	# get the value of the client-id
	client_id = response_message['client-id']


	# send a GET request to ManagerNode, using the client_id Authorization header
	r = requests.get('http://localhost:7777/coord/location/lab308', headers={'Authorization': client_id})

	# decode the message and print
	# note that ManagerNode is only able to provide information as RDF triples, JSON-LD format will be added
	response_message = r.content.decode('ascii').split('\n')
	print(json.dumps(response_message, indent=4))

#### Client