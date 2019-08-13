from __future__ import division

import time
import uuid

import threading

import rdflib
import requests
import roslibpy
import yaml
from webthing.server import ActionsHandler, ThingsHandler, ThingHandler, PropertiesHandler, PropertyHandler, \
    ActionHandler, ActionIDHandler, EventsHandler, EventHandler
from webthing import (Property, MultipleThings, Thing, Value, Action)

import logging
import json

from zeroconf import ServiceInfo, Zeroconf
from services import ActuationService, AvailabilityService
from thingwrapper import ThingWrapper
import tornado.concurrent
import tornado.gen
import tornado.httpserver
import tornado.ioloop
import tornado.web
import tornado.websocket
import socket
from webthing.utils import get_addresses, get_ip

href_counter = 0  # TODO find solution to remove counter

stream = open('sensornode_config.yaml')
config = yaml.load(stream)


class ExtendedThingsHandler(ThingsHandler):

    def initialize(self, things, hosts, ros_client):
        """
        Initialize the handler.

        things -- list of Things managed by this server
        hosts -- list of allowed hostnames
        ros_client -- the Websocket-based ROSBridge client
            for communicating with underlying ROS platform
        """
        super(ExtendedThingsHandler,self).initialize(things, hosts)
        self.ros_client = ros_client

    def post(self):
        try:
            message = json.loads(self.request.body.decode())
        except ValueError:
            self.set_status(400)
            return

        if '@type' not in message:
            self.set_status(400)
            return
        if 'name' not in message:
            self.set_status(400)
            return
        if 'description' not in message:
            self.set_status(400)
            return

        thing_type = message['@type']
        thing_name = message['name']
        thing_description = message['description']

        thing = ThingWrapper(thing_name, thing_type, self.ros_client, thing_description)

        if 'properties' in message:
            thing_properties = message['properties']
            for thing_property in thing_properties:
                property_data = thing_properties[thing_property]

                if 'name' not in property_data:
                    self.set_status(400)
                    return
                if 'value' not in property_data:
                    self.set_status(400)
                    return

                property_name = property_data['name']
                property_value = property_data['value']
                if 'metadata' in property_data:
                    property_metadata = property_data['metadata']
                    thing.add_property(
                        Property(thing,
                                 property_name,
                                 Value(property_value),
                                 property_metadata)
                    )
                else:
                    thing.add_property(
                        Property(thing,
                                 property_name,
                                 Value(property_value))
                    )

        if 'actions' in message:
            thing_actions = message['actions']
            for thing_action in thing_actions:
                action_data = thing_actions[thing_action]

                if 'name' not in action_data:
                    self.set_status(400)
                    return
                if 'metadata' not in action_data:
                    self.set_status(400)
                    return

                action_name = action_data['name']
                action_meta = action_data['metadata']
                thing.add_available_action(action_name, action_meta)

        global href_counter
        thing.set_href_prefix('/{}'.format(href_counter))
        href_counter = href_counter + 1

        """
        self.things -> a things container called MultipleThings object in manager_node
        self.things.things -> things list in the MultipleThings object of manager_node
        """
        self.things.things.append(
            thing)
        # TODO decode Events

    def get(self):
        if 'format' in self.request.arguments:
            format = self.request.arguments['format'][0].decode('ascii')

            # TODO change to match ontology support
            self.set_header('Content-Type', 'application/json')
            ws_href = '{}://{}'.format(
                'wss' if self.request.protocol == 'https' else 'ws',
                self.request.headers.get('Host', '')
            )

            if format == 'json-ld':
                descriptions = []
                for thing in self.things.get_things():
                    description = thing.as_thing_description()
                    description['forms'].append({
                        'rel': 'alternate',
                        'href': '{}{}'.format(ws_href, thing.get_href()),
                    })
                    descriptions.append(description)
                self.write(json.dumps(descriptions))

        else:
            descriptions = ''
            for thing in self.things.get_things():
                description = thing.as_ontology_description()
                descriptions += description
            self.write(descriptions)


class ExtendedThingHandler(ThingHandler):

    @tornado.gen.coroutine
    def get(self, thing_id='0'):
        thing = self.get_thing(thing_id)
        if 'format' in self.request.arguments:
            # TODO change to match ontology support
            if thing is None:
                self.set_status(404)
                self.finish()
                return

            if self.request.headers.get('Upgrade', '').lower() == 'websocket':
                yield tornado.websocket.WebSocketHandler.get(self)
                return

            self.set_header('Content-Type', 'application/json')
            ws_href = '{}://{}'.format(
                'wss' if self.request.protocol == 'https' else 'ws',
                self.request.headers.get('Host', '')
            )

            format = self.request.arguments['format'][0].decode('ascii')
            description = ''
            if format == 'json-ld':
                description = thing.as_thing_description()
                description['forms'].append({
                    'rel': 'alternate',
                    'href': '{}{}'.format(ws_href, thing.get_href()),
                })
                description['base'] = '{}://{}{}'.format(
                    self.request.protocol,
                    self.request.headers.get('Host', ''),
                    thing.get_href()
                )
                description['securityDefinitions'] = {
                    'nosec_sc': {
                        'scheme': 'nosec',
                    },
                }
                description['security'] = 'nosec_sc'

                self.write(json.dumps(description))

        else:
            description = thing.as_ontology_description()
            self.write(description)
        self.finish()


class ExtendedPropertiesHandler(PropertiesHandler):

    def get(self, thing_id='0'):

        if 'format' in self.request.arguments:
            format = self.request.arguments['format'][0].decode('ascii')

            if format == 'json-ld':
                thing = self.get_thing(thing_id)
                if thing is None:
                    self.set_status(404)
                    return

                self.set_header('Content-Type', 'application/json')
                self.write(json.dumps(thing.get_properties()))
        else:
            description = ''

            thing = self.get_thing(thing_id)
            if thing is None:
                self.set_status(404)
                return

            graph = rdflib.Graph()
            rdf = rdflib.namespace.RDF

            bnode = rdflib.BNode()
            graph.add((bnode, rdf.type, rdf.Seq))

            property_dict = thing.get_properties()
            for property_name in property_dict.keys():
                property_url = rdflib.URIRef('http://{}:{}/{}/properties/{}'.format(config['hostname'], config['port'], thing_id, property_name))
                graph.add((bnode, rdf.li, property_url))
                value = rdflib.Literal(property_dict[property_name])
                graph.add( (property_url, rdf.value, value) )

            self.write(graph.serialize(format='nt'))


class ExtendedPropertyHandler(PropertyHandler):
    def get(self, thing_id='0', property_name=None):
        thing = self.get_thing(thing_id)

        if 'format' in self.request.arguments:
            format = self.request.arguments['format'][0].decode('ascii')

            if format == 'json-ld':
                if thing is None:
                    self.set_status(404)
                    return

                if thing.has_property(property_name):
                    self.set_header('Content-Type', 'application/json')
                    self.write(json.dumps({
                        property_name: thing.get_property(property_name),
                    }))
                else:
                    self.set_status(404)
        else:
            graph = rdflib.Graph()
            rdf = rdflib.namespace.RDF

            property_url = rdflib.URIRef('http://localhost:8888/{}/properties/{}'.format(thing_id, property_name))  #TODO hardcoded
            value = rdflib.Literal(thing.get_property(property_name))
            graph.add((property_url, rdf.value, value))

            self.write(graph.serialize(format='nt'))


class SensorNode:
    def __init__(self, things, ros_client, port=80, hostname=None, ssl_options=None,
                 additional_routes=None):
        """
            adapted webthing.server.WebThingServer things manager
                changed ThingsHandler in 'handlers' with ExtendedThingsHandler
        """
        self.things = things

        self.ros_client = ros_client
        self.ros_client.run()

        self.name = things.get_name()
        self.port = port
        self.hostname = hostname

        system_hostname = socket.gethostname().lower()
        self.hosts = [
            'localhost',
            'localhost:{}'.format(self.port),
            '{}.local'.format(system_hostname),
            '{}.local:{}'.format(system_hostname, self.port),
        ]

        for address in get_addresses():
            self.hosts.extend([
                address,
                '{}:{}'.format(address, self.port),
            ])

        if self.hostname is not None:
            self.hostname = self.hostname.lower()
            self.hosts.extend([
                self.hostname,
                '{}:{}'.format(self.hostname, self.port),
            ])

        for idx, thing in enumerate(self.things.get_things()):
            thing.set_href_prefix('/{}'.format(idx))

        handlers = [
            (
                r'/?',
                ExtendedThingsHandler,
                dict(things=self.things, hosts=self.hosts, ros_client=self.ros_client),
            ),
            (
                r'/(?P<thing_id>\d+)/?',
                ExtendedThingHandler,
                dict(things=self.things, hosts=self.hosts),
            ),
            (
                r'/(?P<thing_id>\d+)/properties/?',
                ExtendedPropertiesHandler,
                dict(things=self.things, hosts=self.hosts),
            ),
            (
                r'/(?P<thing_id>\d+)/properties/' +
                r'(?P<property_name>[^/]+)/?',
                ExtendedPropertyHandler,
                dict(things=self.things, hosts=self.hosts),
            ),
            (
                r'/(?P<thing_id>\d+)/actions/?',
                ActionsHandler,
                dict(things=self.things, hosts=self.hosts),
            ),
            (
                r'/(?P<thing_id>\d+)/actions/(?P<action_name>[^/]+)/?',
                ActionHandler,
                dict(things=self.things, hosts=self.hosts),
            ),
            (
                r'/(?P<thing_id>\d+)/actions/' +
                r'(?P<action_name>[^/]+)/(?P<action_id>[^/]+)/?',
                ActionIDHandler,
                dict(things=self.things, hosts=self.hosts),
            ),
            (
                r'/(?P<thing_id>\d+)/events/?',
                EventsHandler,
                dict(things=self.things, hosts=self.hosts),
            ),
            (
                r'/(?P<thing_id>\d+)/events/(?P<event_name>[^/]+)/?',
                EventHandler,
                dict(things=self.things, hosts=self.hosts),
            ),
        ]


        if isinstance(additional_routes, list):
            handlers = additional_routes + handlers

        self.app = tornado.web.Application(handlers)
        self.app.is_tls = ssl_options is not None
        self.server = tornado.httpserver.HTTPServer(self.app,
                                                    ssl_options=ssl_options)

    def start(self):
        """Start listening for incoming connections."""
        self.service_info = ServiceInfo(
            '_webthing._tcp.local.',
            '{}._webthing._tcp.local.'.format(self.name),
            address=socket.inet_aton(get_ip()),
            port=self.port,
            properties={
                'path': '/',
            },
            server='{}.local.'.format(socket.gethostname()))
        self.zeroconf = Zeroconf()
        self.zeroconf.register_service(self.service_info)

        self.server.listen(self.port)
        tornado.ioloop.IOLoop.current().start()

    def stop(self):
        """Stop listening."""
        self.zeroconf.unregister_service(self.service_info)
        self.zeroconf.close()
        self.server.stop()


"""
  //////////////////////
 ////   SERVICES   ////
//////////////////////
"""


class HueLampActuation(ActuationService):
    def ros_actuation(self, payload):
        talker = roslibpy.Topic(self.thing.client, '/lights_1', 'std_msgs/String')
        talker.publish(roslibpy.Message(payload))


class BlindsActuation(ActuationService):
    def ros_actuation(self, payload):
        talker = roslibpy.Topic(self.thing.client, '/blinds_1', 'std_msgs/Int32')
        talker.publish(roslibpy.Message(payload))


class HueLightAvailability(AvailabilityService):
    def check_availability(self):
        client = self.thing.client

        service = roslibpy.Service(client, config['hue_lamp_availability_ROSservice_name'], config['hue_lamp_availability_ROSservice_type'])

        request = roslibpy.ServiceRequest({})
        result = service.call(request)

        return result['is_available']

    def listen_availability(self):
        # TODO
        raise NotImplementedError


class Blinds1Availability(AvailabilityService):
    def check_availability(self):
        client = self.thing.client

        service = roslibpy.Service(client, config['blinds1_availability_ROSservice_name'], config['blinds1_lamp_availability_ROSservice_type'])

        request = roslibpy.ServiceRequest({})
        result = service.call(request)

        return result['is_available']

    def listen_availability(self):
        # TODO
        raise NotImplementedError


class AlwaysTrue(AvailabilityService):
    def check_availability(self):
        return True

    def listen_availability(self):
        self.thing.set_property('available', True)


"""
  //////////////////////
 ////   HUE LAMP   ////
//////////////////////
"""


class OnAction(Action):
    def __init__(self, thing, input_):
        Action.__init__(self, uuid.uuid4().hex, thing, 'on', input_=input_)

    def perform_action(self):
        actuation_service = HueLampActuation(self.thing)
        payload = {'data': json.dumps({'power': 'on'})}

        actuation_service.ros_actuation(payload)

        self.thing.set_property('on', True)
        print('ToglleAction performed on ' + self.thing.name)


class OffAction(Action):
    def __init__(self, thing, input_):
        Action.__init__(self, uuid.uuid4().hex, thing, 'off', input_=input_)

    def perform_action(self):
        actuation_service = HueLampActuation(self.thing)
        payload = {'data': json.dumps({'power': 'off'})}
        actuation_service.ros_actuation(payload)

        self.thing.set_property('on', False)
        print('ToglleAction performed on ' + self.thing.name)


class ChangeColor(Action):
    def __init__(self, thing, input_):
        Action.__init__(self, uuid.uuid4().hex, thing, 'color', input_=input_)

    def perform_action(self):
        actuation_service = HueLampActuation(self.thing)
        color = self.input['color']

        payload = {'data': json.dumps({'color': color})}
        actuation_service.ros_actuation(payload)

        self.thing.set_property('color', color)


def make_hue_light(client):
    thing_type = 'HueLight'
    base_uri = config['lab308_things_ontology_path'] #TODO hardcoded
    thing = ThingWrapper('hue_lamp', thing_type, base_uri, client, AlwaysTrue, 'Philips HUE as web thing')    # TODO change AlwaysTrue with HueLightAvailability

    thing.add_property(
        Property(thing,
                 'on',
                 Value(False),
                 metadata={
                     '@type': 'OnOffProperty',
                     'title': 'On/Off',
                     'type': 'boolean',
                     'description': 'Whether the lamp is turned on',
                 }))
    thing.add_property(
        Property(thing,
                 'color',
                 Value(None),
                 metadata={
                     '@type': 'ColorProperty',
                     'title': 'Color',
                     'type': 'string',
                     'description': 'Lamp color',
                 }))

    thing.add_available_action('color',
                               {
                                   'title': 'Change color',
                                   'description': 'Change color',
                                   'metadata': {
                                       'input':{
                                           'color' : 'xsd:string'
                                       }
                                   }
                               },
                               ChangeColor)

    thing.add_available_action('on',
                               {
                                   'title': 'Turn on',
                                   'description': 'Turn the lamp on or off',
                                   'metadata': {}
                               },
                               OnAction)
    thing.add_available_action('off',
                               {
                                   'title': 'turn off',
                                   'description': 'Turn the lamp on or off',
                                   'metadata': {}
                               },
                               OffAction)
    return thing


"""
  //////////////////////
 ////   BLINDS   //////
//////////////////////
"""


class BlindsUp(Action):
    def __init__(self, thing, input_):
        Action.__init__(self, uuid.uuid4().hex, thing, 'up', input_=input_)

    def perform_action(self):
        actuation_service = BlindsActuation(self.thing)
        payload = {'data': 1}

        actuation_service.ros_actuation(payload)


class BlindsDown(Action):
    def __init__(self, thing, input_):
        Action.__init__(self, uuid.uuid4().hex, thing, 'down', input_=input_)

    def perform_action(self):
        actuation_service = BlindsActuation(self.thing)
        payload = {'data': -1}

        actuation_service.ros_actuation(payload)


class BlindsStop(Action):
    def __init__(self, thing, input_):
        Action.__init__(self, uuid.uuid4().hex, thing, 'stop', input_=input_)

    def perform_action(self):
        actuation_service = BlindsActuation(self.thing)
        payload = {'data': 0}

        actuation_service.ros_actuation(payload)


def make_blinds1(client):
    thing_type = 'Blinds'
    base_uri = config['lab308_things_ontology_path'] #TODO hardcoded

    thing = ThingWrapper('blinds_1',thing_type, base_uri, client, AlwaysTrue, 'AI-MAS blinds as web thing')

    thing.add_available_action('up',
                               {
                                   'title': 'BlindsUp',
                                   'description': 'Start to rise the blinds',
                                   'metadata':{}
                               },
                               BlindsUp)

    thing.add_available_action('down',
                               {
                                   'title': 'BlindsDown',
                                   'description': 'Start to lower the blinds',
                                   'metadata':{}
                               },
                               BlindsDown)

    thing.add_available_action('stop',
                               {
                                   'title': 'BlindsStop',
                                   'description': 'Stop the blinds',
                                   'metadata':{}
                               },
                               BlindsDown)

    return thing

"""
  //////////////////
 ////   RUN   /////
//////////////////
"""


def run_server():

    # client = roslibpy.Ros(host='192.168.0.158', port=9090) # Lab ROS
    client = roslibpy.Ros(host=config['ros_host'], port=config['ros_port'])

    hue_light = make_hue_light(client)
    blinds1 = make_blinds1(client)
    things = [hue_light, blinds1]

    server = SensorNode(MultipleThings(things, config['things_container_name']), ros_client= client, port=config['port'], hostname=config['hostname'])
    try:
        logging.info('starting the server')
        server.start()
    except KeyboardInterrupt:
        logging.info('stopping the server')
        server.stop()
        logging.info('done')


def join_at_manager():
    time.sleep(5)

    get_store_request = requests.get('http://{}:{}'.format(config['hostname'], config['port']))
    triple_store = get_store_request.content.decode('ascii')

    join_request = requests.post('{}/join'.format(config['manager_node_url']), data = triple_store)


if __name__ == '__main__':
    logging.basicConfig(
        level=20,
        format="[SENSOR NODE]  %(asctime)s %(filename)s:%(lineno)s %(levelname)s %(message)s"
    )

    server_thread = threading.Thread(target=join_at_manager)
    server_thread.start()

    run_server()
