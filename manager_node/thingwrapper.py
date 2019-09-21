import uuid
from webthing import Action, Value, Property

from jsonschema import validate
from jsonschema.exceptions import ValidationError

from services import ActuationService
import owlready2
import rdflib

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
        super(ThingWrapper, self).__init__(name, title=name, type_=type_, description=description)
        self.type = type_
        self.client = client
        self.base_uri = base_uri
        self.talkers = {}

        self.availability_service = availability_cls(self)
        self.availability_service.start_listening()
        # self.add_property(Property(self, 'available', Value(self.availability_service.check_availability())))
        availability = self.availability_service.check_availability()
        self.add_property(Property(self, 'available', Value(availability)))
        self.add_available_event('Available', None)

    def as_thing_description(self):
        thing = {
            'id': self.id,
            'title': self.title,
            '@context': {
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
        ontology = self.ontology_description()
        return ontology

    def ontology_description(self):
        td = owlready2.get_ontology("../ontology/td.owl").load()
        context_domain_org = owlready2.get_ontology(
            "../ontology/context-domain-org.owl").load()

        ontology = owlready2.get_ontology(self.base_uri).load()

        thing_iri = 'http://localhost:8888' + self.href_prefix  # TODO hardcoded

        if ontology.world.get(iri=thing_iri) is None:
            object_class = ontology.__getitem__(self.type)
            thing = object_class(iri=thing_iri)
            thing.is_a.append(td.Thing)
            thing.title.append(self.title)

            thing_properties = self.get_property_descriptions()
            properties = []
            for property in thing_properties:
                property_affordance = td.PropertyAffordance(iri='{}/properties/{}'.format(thing.iri, property))
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

                action_affordance = td.ActionAffordance(iri='{}/actions/{}'.format(thing.iri, name))
                action_affordance.hasInputSchema = input_schemas
                actions.append(action_affordance)

            thing_events = self.available_events
            events = []
            for event_name in thing_events.keys():
                event_affordance = td.EventAffordance(iri='{}/events/{}'.format(thing.iri, event_name))
                event_affordance.is_a.append(context_domain_org.ThingAvailableEvent)
                events.append(event_affordance)

            thing.hasActionAffordance = actions
            thing.hasPropertyAffordance = properties
            thing.hasEventAffordance = events

            if ontology.world.get(iri='http://localhost:8888') is None:
                sensor_agent = context_domain_org.SensorAgent(iri='http://localhost:8888')  # TODO hardcoded
            else:
                sensor_agent = ontology.world.get(iri='http://localhost:8888')
            sensor_agent.managesThing.append(thing)

            graph = ontology.world.as_rdflib_graph()

            uri = rdflib.URIRef(ontology.base_iri + self.type)
            ontology_str = ''

            query = " CONSTRUCT { ?sensorAgent <http://pervasive.semanticweb.org/ont/2019/07/consert/context-domain-org#managesThing> ?thing . } WHERE { ?sensorAgent <http://pervasive.semanticweb.org/ont/2019/07/consert/context-domain-org#managesThing> ?thing . } "
            r = list(graph.query(query))
            for triple in r:
                triple_str = ''
                for triple_element in triple:
                    if (str(triple_element).startswith('http')):
                        triple_str += '<' + str(triple_element) + '> '
                    else:
                        triple_str += '"' + str(triple_element) + '" '
                ontology_str += triple_str + '.\n'

            query = " CONSTRUCT {{ ?name ?hasProperty ?Property}} WHERE {{ ?name ?hasProperty ?Property . ?name a <{}> }} ".format(
                uri, uri, uri, uri, uri)
            r = list(graph.query(query))
            for triple in r:
                triple_str = ''
                for triple_element in triple:
                    if (str(triple_element).startswith('http')):
                        triple_str += '<' + str(triple_element) + '> '
                    else:
                        triple_str += '"' + str(triple_element) + '" '
                ontology_str += triple_str + '.\n'

            query = " CONSTRUCT {{ ?property ?hasData ?data . }} WHERE {{ ?property ?hasData ?data . ?name ?p ?property . ?name a <{}> . }} ".format(
                uri)
            r = list(graph.query(query))
            for triple in r:
                triple_str = ''
                for triple_element in triple:
                    if (str(triple_element).startswith('http')):
                        triple_str += '<' + str(triple_element) + '> '
                    else:
                        triple_str += '"' + str(triple_element) + '" '
                ontology_str += triple_str + '.\n'

            query = " CONSTRUCT {{ ?data ?p ?o }} WHERE {{ ?data ?p ?o . ?property ?hasData ?data . ?name ?hasProperty ?property . ?name a <{}> . }} ".format(
                uri)
            r = list(graph.query(query))
            for triple in r:
                triple_str = ''
                for triple_element in triple:
                    if (str(triple_element).startswith('http')):
                        triple_str += '<' + str(triple_element) + '> '
                    else:
                        triple_str += '"' + str(triple_element) + '" '
                ontology_str += triple_str + '.\n'

            # return graph.serialize(format="turtle", indent=4).decode("ascii")
            return ontology_str
        else:
            graph = ontology.world.as_rdflib_graph()
            thing_url = rdflib.URIRef(thing_iri)

            ontology_str = ''

            query = " CONSTRUCT {{ <{}> ?hasProperty ?property . }} WHERE {{ <{}> ?hasProperty ?property . }} ".format(
                thing_url, thing_url)
            r = list(graph.query(query))
            for triple in r:
                triple_str = ''
                for triple_element in triple:
                    if str(triple_element).startswith('http'):
                        triple_str += '<' + str(triple_element) + '> '
                    else:
                        triple_str += '"' + str(triple_element) + '" '
                ontology_str += triple_str + '.\n'

            query = " CONSTRUCT {{ ?property ?hasData ?data . }} WHERE {{ <{}> ?hasProperty ?property . ?property ?hasData ?data . }} ".format(
                thing_url)
            r = list(graph.query(query))
            for triple in r:
                triple_str = ''
                for triple_element in triple:
                    if str(triple_element).startswith('http'):
                        triple_str += '<' + str(triple_element) + '> '
                    else:
                        triple_str += '"' + str(triple_element) + '" '
                ontology_str += triple_str + '.\n'
            return ontology_str

    def set_availability(self, state):
        self.set_property('available', state)

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
