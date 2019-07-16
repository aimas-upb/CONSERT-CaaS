from __future__ import division
from webthing import (Action, Property, MultipleThings, Thing, Value,
                      WebThingServer)
import logging
import roslibpy
import time
import uuid
import json

client = roslibpy.Ros(host='192.168.0.158', port=9090)
client.run()
talker0 = roslibpy.Topic(client, '/lights_1', 'std_msgs/String')
"""
//////////////////////////
////   HUE_LAMP CODE  ////
//////////////////////////
"""

"""AVAILABLE ACTIONS"""

class OnAction(Action):
    def __init__(self, thing, input_):
        Action.__init__(self, uuid.uuid4().hex, thing, 'on', input_=input_)

    def perform_action(self):
        payload = {'data': json.dumps({'power': 'on'})}

        talker0.publish(roslibpy.Message(payload))
        self.thing.set_property('on', True)

        print('ToglleAction performed')


class OffAction(Action):
    def __init__(self, thing, input_):
        Action.__init__(self, uuid.uuid4().hex, thing, 'off', input_=input_)

    def perform_action(self):

        payload = {'data': json.dumps({'power': 'off'})}

        talker0.publish(roslibpy.Message(payload))
        self.thing.set_property('on', False)

        print('ToglleAction performed')


class ChangeColor(Action):
    def __init__(self, thing, input_):
        Action.__init__(self, uuid.uuid4().hex, thing, 'color', input_=input_)

    def perform_action(self):
        color = self.input['color']

        print('Color changed to: ' + color)
        data = {
            'data':
                json.dumps(
                    {
                        'color': color
                    }
                )
            }
        talker0.publish(roslibpy.Message(data))
        self.thing.set_property('color', color)


def make_hue_lamp_thing():
    # thing init #
    thing_type = ['OnOffSwitch', 'Light']
    thing = Thing(
        'lights_1',
        'hue_lamp',
        thing_type,
    )

    # thind properties #
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
                 'brightness',
                 Value(0),
                 metadata={
                     '@type': 'BrightnessProperty',
                     'title': 'Brightness',
                     'type': 'integer',
                     'description': 'The level of light from 0-100',
                     'minimum': 0,
                     'maximum': 100,
                     'unit': 'percent',
                 })
    )

    thing.add_property(
        Property(thing,
                 'color',
                 Value('white'),
                 metadata={
                     '@type': 'Color',
                     'title': 'Light color',
                     'type': 'string',
                     'description': 'Lamp Color',
                 }))

    # thing actions #
    thing.add_available_action('on',
                               {
                                   'title': 'OnAction',
                                   'description': 'Turn the lamp on',
                                   'metadata': {
                                       'input': {
                                           'type': 'None'
                                       }
                                   }
                               },
                               OnAction)

    thing.add_available_action('off',
                               {
                                   'title': 'OffAction',
                                   'description': 'Turn the lamp off',
                                   'metadata': {
                                       'input': {
                                           'type': 'None'
                                       }
                                   }
                               },
                               OffAction)

    thing.add_available_action('color',
                               {
                                   'title': 'ChangeColor',
                                   'description': 'Change hue_light color',
                                   'metadata': {
                                       'input': {
                                           'type': 'object',
                                           'required': ['color']
                                       }
                                   }
                               },
                               ChangeColor)
    return thing


"""
//////////////////////////
////    BLINDS CODE   ////
//////////////////////////
"""


class blinds_up(Action):
    def __init__(self, thing, input_):
        Action.__init__(self, uuid.uuid4().hex, thing, 'blinds_up', input_=input_)

    def perform_action(self):
        talker0.publish(roslibpy.Message({'data': 1}))
        time.sleep(1)

        print('Se ridica jaluzelele')


class blinds_down(Action):
    def __init__(self, thing, input_):
        Action.__init__(self, uuid.uuid4().hex, thing, 'blinds_down', input_=input_)

    def perform_action(self):
        talker0.publish(roslibpy.Message({'data': -1}))
        time.sleep(1)

        print('Se coboara jaluzelele')


class blinds_stop(Action):
    def __init__(self, thing, input_):
        Action.__init__(self, uuid.uuid4().hex, thing, 'blinds_stop', input_=input_)

    def perform_action(self):
        talker0.publish(roslibpy.Message({'data': 0}))
        time.sleep(1)

        print('Se opresc jaluzelele')


def make_blinds1_thing():
    thing_type = ['UpDownStop', 'Blinds1']
    thing = Thing('blinds_2',
                  'blinds',
                  thing_type)

    thing.add_available_action(
        'blinds_up',
        {
            'title': 'Blinds up',
            'description': 'Rise the blinds',
            'metadata': {
                'input': 'None'
            }
        },
        blinds_up
    )

    thing.add_available_action(
        'blinds_down',
        {
            'title': 'Blinds down',
            'description': 'Lower the blinds',
            'metadata': {
                'input': 'None'
            }
        },
        blinds_down
    )

    thing.add_available_action(
        'blinds_stop',
        {
            'title': 'Blinds stop',
            'description': 'Stop the blinds',
            'metadata': {
                'input': 'None'
            }
        },
        blinds_stop
    )

    return thing


def make_blinds2_thing():
    thing_type = ['UpDownStop', 'Blinds2']
    thing = Thing('blinds_2',
                  'blinds',
                  thing_type)

    thing.add_available_action(
        'blinds_up',
        {
            'title': 'Blinds up',
            'description': 'Rise the blinds',
            'metadata': {
                'input': 'None'
            }
        },
        blinds_up
    )

    thing.add_available_action(
        'blinds_down',
        {
            'title': 'Blinds down',
            'description': 'Lower the blinds',
            'metadata': {
                'input': 'None'
            }
        },
        blinds_down
    )

    thing.add_available_action(
        'blinds_stop',
        {
            'title': 'Blinds stop',
            'description': 'Stop the blinds',
            'metadata': {
                'input': 'None'
            }
        },
        blinds_stop
    )

    return thing


def run_multiple_things_server():
    hue_lamp = make_hue_lamp_thing()
    blinds1 = make_blinds1_thing()
    blinds2 = make_blinds2_thing()
    things = [hue_lamp, blinds1, blinds2]

    server = WebThingServer(MultipleThings(things, 'AI-MAS LAB'), port=8888)

    try:
        logging.info('starting the server')
        server.start()

    except KeyboardInterrupt:
        talker0.unadvertise()
        client.terminate()

        logging.info('stopping the server')
        server.stop()
        logging.info('done')


if __name__ == '__main__':
    logging.basicConfig(
        level=10,
        format="%(asctime)s %(filename)s:%(lineno)s %(levelname)s %(message)s"
    )
    run_multiple_things_server()
