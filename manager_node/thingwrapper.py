import threading
import time
import uuid
from webthing import Action, Value, Property

from jsonschema import validate
from jsonschema.exceptions import ValidationError

from services import AvailabilityService, ActuationService
import roslibpy
import webthing


class PerformROSAction(Action):
    def __init__(self, thing, action_name, input_):
        Action.__init__(self, uuid.uuid4().hex, thing, action_name, input_=input_)

    def perform_action(self):
        """
            data = message to be sent via ros
        """
        print("({}) Started action: ".format(self.thing.name) + self.name)  # TODO remove when done

        if 'default_ROS_value' in self.thing.available_actions[self.name]['metadata']:
            data = self.thing.available_actions[self.name]['metadata']['default_ROS_value']
            ActuationService.ros_actuation(self.thing,
                                           self.thing.talkers[self.name],
                                           data)

        elif 'ROS' in self.input:
            data = self.input['ROS']['data']
            ActuationService.ros_actuation(self.thing,
                                           self.thing.talkers[self.name],
                                           data)
        # TODO sent some message if no condition was

        print("({}) Finished action: ".format(self.thing.name) + self.name)  # TODO remove when done


class ThingWrapper(webthing.Thing):

    def __init__(self, name, type_, client, availability_cls, description=''):
        super(ThingWrapper, self).__init__(name, type_, description)
        self.client = client
        self.talkers = {}
        self.availability_service = availability_cls(self)

        self.add_property(
            Property(self,
                     'available',
                     Value(self.availability_service.check_availability()))
        )  # TODO check to inintial value using check_availability (see services)

        #availabilityService = AvailabilityService(self.client)
        #availabilityService.listen_availability(self)

    """
    def set_availability(self, request, response):
        state = request['data']
        self.set_property('available', state)
        response['success'] = True
        print(self.name + " availabilty set to: {}".format(request['data']))
        return True
     """
    def set_availability(self, state):
        self.set_property('available', state)
        print("Setting " + self.name + " to".format(state))

    def add_available_action(self, name, metadata, cls=None):

        if cls:
            super(ThingWrapper, self).add_available_action(name, metadata, cls)
        else:
            talker = roslibpy.Topic(self.client, metadata['topic'], metadata['message_type'])
            self.talkers[name] = talker

            super(ThingWrapper, self).add_available_action(name, metadata, PerformROSAction)

    def perform_action(self, action_name, input_=None):
        if action_name not in self.available_actions:
            return None

        action_type = self.available_actions[action_name]

        if 'input' in action_type['metadata']:
            try:
                validate(input_, action_type['metadata']['input'])
            except ValidationError:
                return None
        if isinstance(action_type['class'], PerformROSAction):

            action = action_type['class'](self, action_name, input_=input_)
            action.set_href_prefix(self.href_prefix)
            self.action_notify(action)
            self.actions[action_name].append(action)
            return action
        else:
            action = super(ThingWrapper, self).perform_action(action_name, input_)
            return action


####################
##### TESTING ######
####################

if __name__ == '__main__':
    thing = ThingWrapper("MyThing", ['type_of_thing'], 'alala')

    while True:
        state = thing.get_property('available')
        print(thing.name + " availability is: {}".format(state))
        time.sleep(5)
