import uuid
from webthing import Action, Value, Property

from jsonschema import validate
from jsonschema.exceptions import ValidationError

from services import AvailabilityService, ActuationService
import owlready2

import roslibpy
import webthing


class PerformROSAction(Action):
    def __init__(self, thing, action_name, input_):
        Action.__init__(self, uuid.uuid4().hex, thing, action_name, input_=input_)

    def perform_action(self):
        if 'default_ROS_value' in self.thing.available_actions[self.name]['metadata']:
            data = self.thing.available_actions[self.name]['metadata']['default_ROS_value']
            ActuationService.ros_actuation(self.thing, data)

        elif 'ROS' in self.input:
            data = self.input['ROS']['data']
            ActuationService.ros_actuation(self.thing, data)


class ThingWrapper(webthing.Thing):
    def __init__(self, name, type_, base_uri, client, availability_cls, description=''):
        super(ThingWrapper, self).__init__(name, name, type_, description)
        self.type = type_
        self.client = client
        self.base_uri = base_uri
        self.talkers = {}
        self.availability_service = availability_cls(self)
        self.add_property(Property(self, 'available', Value(self.availability_service.check_availability())))

    def as_thing_description(self):
        """
        Return the thing state as a Thing Description.

        Returns the state as a dictionary.
        """
        thing = {
            'id': self.id,
            'title': self.title,
            '@context':{
                'base_URI': self.base_uri
            },
            'href': self.href_prefix if self.href_prefix else '/',
            '@type': self.type,
            'properties': self.get_property_descriptions(),
            'actions': {},
            'events': {},
            'forms': [
                {
                    'rel': 'properties',
                    'href': '{}/properties'.format(self.href_prefix),
                    'cov:methodName': 'GET'
                },
                {
                    'rel': 'actions',
                    'href': '{}/actions'.format(self.href_prefix),
                    'cov:methodName': 'GET'
                },
                {
                    'rel': 'events',
                    'href': '{}/events'.format(self.href_prefix),
                    'cov:methodName': 'GET'
                },
            ],
        }

        for property in thing['properties']:
            thing['properties'][property]['forms'] = thing['properties'][property].pop('links')
            thing['properties'][property]['forms'][0]['cov:methodName'] = 'GET'

        for name, action in self.available_actions.items():
            thing['actions'][name] = action['metadata']
            thing['actions'][name]['forms'] = [
                {
                    'rel': 'action',
                    'href': '{}/actions/{}'.format(self.href_prefix, name),
                    'cov:methodName': 'POST'
                },
            ]

        for name, event in self.available_events.items():
            thing['events'][name] = event['metadata']
            thing['events'][name]['forms'] = [
                {
                    'rel': 'event',
                    'href': '{}/events/{}'.format(self.href_prefix, name),
                },
            ]

        if self.ui_href is not None:
            thing['forms'].append({
                'rel': 'alternate',
                'mediaType': 'text/html',
                'href': self.ui_href,
                'cov:methodName': 'GET'
            })

        if self.description:
            thing['description'] = self.description

        return thing

    def as_ontology_description(self):
        print(self.title)  # testing

        td = owlready2.get_ontology("file:///home/costin/Desktop/ontology/td.owl").load()
        ontology = owlready2.get_ontology(self.base_uri).load()

        object_class = ontology.__getitem__(self.type)
        thing = object_class(self.title)
        thing.title= self.title

        thing_properties = self.get_property_descriptions()
        properties = []
        for property in thing_properties:
            property_affordance = td.PropertyAffordance(self.title + "_" + property + "_property")
            properties.append(property_affordance)

        thing_actions = self.available_actions.items()
        actions = []
        for name, action in thing_actions:
            input_schemas = []
            if action['metadata']['metadata']:
                for input_param_name in action['metadata']['metadata']['input']:
                    input_schema = ontology.InputSchema(self.title + "_" + name + "_action_inputSchema")
                    input_schema.title = input_param_name
                    input_schema.type.append(action['metadata']['metadata']['input'][input_param_name])

                    input_schemas.append(input_schema)
            action_affordance = td.ActionAffordance(self.title + "_" + name + "_action_")
            action_affordance.hasInputSchema = input_schemas
            actions.append(action_affordance)

        thing.hasActionAffordance = actions
        thing.hasPropertyAffordance = properties

        graph = ontology.world.as_rdflib_graph()
        return graph.serialize(format="turtle", indent=4).decode("ascii")

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

        if not self.get_property('available'):
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