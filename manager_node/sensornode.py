from __future__ import division

import uuid

import roslibpy
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

href_counter = 0  #TODO find solution to remove counter

#TODO add if_available service on perform_action

class ExtendedThingsHandler(ThingsHandler):

    # def __init__(self, *args, **kwargs):
    #     super(ExtendedThingsHandler, self).__init__(*args, **kwargs)

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


class SensorNode:
    def __init__(self, things, ros_client, port=80, hostname=None, ssl_options=None,
                 additional_routes=None):
        """
            adapted webthing.server.WebThingServer things manager
                changed ThingsHandler in 'handlers' with ExtendedThingsHandler
                added 'href_counter' param for href assignment
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
                dict(things=self.things, hosts=self.hosts, ros_client=self.ros_client), #TODO adapted for testing
            ),
            (
                r'/(?P<thing_id>\d+)/?',
                ThingHandler,
                dict(things=self.things, hosts=self.hosts),
            ),
            (
                r'/(?P<thing_id>\d+)/properties/?',
                PropertiesHandler,
                dict(things=self.things, hosts=self.hosts),
            ),
            (
                r'/(?P<thing_id>\d+)/properties/' +
                r'(?P<property_name>[^/]+)/?',
                PropertyHandler,
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
        talker = roslibpy.Topic(self.thing.client, '/lights_1', 'std_msgs/String') #TODO change topic
        talker.publish(roslibpy.Message(payload))


class BlindsActuation(ActuationService):
    def ros_actuation(self, payload):
        talker = roslibpy.Topic(self.thing.client, '/blinds_1', 'std_msgs/Int32')
        talker.publish(roslibpy.Message(payload))


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
    thing_type = ['OnOffSwitch', 'Light',  'Philips HUE']

    thing = ThingWrapper('hue_lamp', thing_type, client, AlwaysTrue, 'Philips HUE as web thing')

    #TODO add 'availablie property'
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
                                   'metadata': {}  # TODO add metadata: input description for 'validate'
                               },
                               ChangeColor)

    thing.add_available_action('on',
                               {
                                   'title': 'Turn on',
                                   'description': 'Turn the lamp on or off',
                                   'metadata':{} #TODO add metadata: input description for 'validate'
                               },
                               OnAction)
    thing.add_available_action('off',
                               {
                                   'title': 'turn off',
                                   'description': 'Turn the lamp on or off',
                                   'metadata': {}  # TODO add metadata: input description for 'validate'
                               },
                               OffAction)
    return thing


"""
  //////////////////////
 ////   BLINDS   //////
//////////////////////
"""
#TODO test blinds


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
    thing_type = ['blinds', 'light change']
    thing = ThingWrapper('blinds_1',thing_type, client, AlwaysTrue, 'AI-MAS blinds as web thing')
    #TODO add available property

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

    #client = roslibpy.Ros(host='192.168.0.158', port=9090)
    client = roslibpy.Ros(host='localhost', port=9090)

    hue_light = make_hue_light(client)
    blinds1 = make_blinds1(client)
    things = [hue_light, blinds1]

    server = SensorNode(MultipleThings(things, "Nume"), client, port=8888)
    try:
        logging.info('starting the server')
        server.start()
    except KeyboardInterrupt:
        logging.info('stopping the server')
        server.stop()
        logging.info('done')


if __name__ == '__main__':
    logging.basicConfig(
        level=10,
        format="%(asctime)s %(filename)s:%(lineno)s %(levelname)s %(message)s"
    )
    run_server()