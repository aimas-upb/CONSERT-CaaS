import logging
import subprocess
import threading

import rdflib
import requests
import time

import owlready2

import json
import uuid

import tornado.web
import tornado.ioloop
import tornado.httpserver
import yaml

stream = open('managernode_config.yaml')
config = yaml.load(stream)


def start_corese_server(corese_server_path):
    # subprocess.call(['java', '-jar', corese_server_path]) # with logging
    subprocess.call(['java', '-jar', '-Dlog4j.configurationFile=file:{}'.format(config['corese_Dlog4j_config_file']),
                     corese_server_path])   # without logging
    # TODO find a way to test if it launched successfully


def load_ontology(url):
    r = requests.get(url)


def start_corese_server_thread():
    corese_server_path = config['corese_server_path']
    corese_server_thread = threading.Thread(target=start_corese_server, args=(corese_server_path,))
    corese_server_thread.start()


class EventListenerHandler(tornado.web.RequestHandler):
    def initialize(self, manager_node):
        self.manager_node = manager_node

    def post(self):
        message = json.loads(self.request.body.decode(encoding='ascii'))

        if 'Available' in message['data']:  # TODO decode 'Available' param from message
            self.manager_node.resource_update('Available', message['data']['Available'])


class BaseHandler(tornado.web.RequestHandler):
    def initialize(self, manager_node):
        self.manager_node = manager_node

    def get(self):
        if 'Authorization' not in self.request.headers:
            self.set_status(401)
            return

        client_id = self.request.headers['Authorization']
        if client_id not in self.manager_node.consumers:
            self.set_status(401)
            return

        format = None

        if 'format' in self.request.arguments:
            format = self.request.arguments['format'][0].decode('ascii')

        if format is None or format == 'ontology':
            self.set_header('Content-Type', 'text/plain')
            description = self.manager_node.as_ontology_description()
            self.write(description)
        elif format == 'json-ld':
            # TODO
            print()
        else:
            self.set_status(400)
            return


class ProvidersHandler(tornado.web.RequestHandler):

    def initialize(self, manager_node):
        self.manager_node = manager_node

    def get(self):
        format = None
        if 'format' in self.request.arguments:
            format = self.request.arguments['format'][0].decode('ascii')

        if format is None or format == 'ontology':
            self.set_header('Content-Type', 'text/plain')
            description = self.manager_node.get_providers_as_rdf()
            self.write(description)
        else:
            # TODO
            print()


class CapabilitiesHandler(tornado.web.RequestHandler):
    def initialize(self, manager_node):
        self.manager_node = manager_node

    def get(self):
        format = None

        if 'format' in self.request.arguments:
            format = self.request.arguments['format'][0].decode('ascii')

        if format is None or format == 'ontology':
            self.set_header('Content-Type', 'text/plain')
            description = self.manager_node.get_capabilities_as_rdf()
            self.write(description)
        else:
            # TODO
            print()


class JoinHandler(tornado.web.RequestHandler):

    def initialize(self, manager_node):
        self.manager_node = manager_node

    def post(self):
        if 'as' not in self.request.arguments:
            self.set_status(400)
            return

        join_type = self.request.arguments['as'][0].decode('ascii')

        if join_type == 'sensor_node':
            sensor_node_uri = self.request.headers['sensor_node_id']
            self.manager_node.sensor_nodes.append(sensor_node_uri)

            new_data = self.request.body.decode(encoding='ascii')

            corese_url = config['corese_url']

            for line in new_data.splitlines():
                payload = {'query': 'INSERT DATA{{ {} }}'.format(line)}
                r = requests.post(corese_url, params=payload)

                # TODO reformat subscribe method:
                if line.endswith('ThingAvailableEvent> .'):
                    subscribe_url = line.split(' ')[0]
                    subscribe_url = subscribe_url[1:-1]
                    subscribe_payload = {
                        'subscriber': 'http://{}:{}/coord/{}/{}/event_listener'.format(self.manager_node.host,
                                                                                       self.manager_node.port,
                                                                                       self.manager_node.context_dimension_type,
                                                                                       self.manager_node.domain_name)
                    }
                    requests.post(subscribe_url, data=json.dumps(subscribe_payload))

            manager_node_uri = '<http://{}:{}/coord/{}/{}> '.format(self.manager_node.host, self.manager_node.port,
                                                                    self.manager_node.context_dimension_type,
                                                                    self.manager_node.domain_name)
            group_member_of_uri = '<http://pervasive.semanticweb.org/ont/2019/07/consert/context-domain-org#groupMemberOf> '
            payload = {
                'query': 'INSERT DATA{{ {} {} {} }}'.format(sensor_node_uri, group_member_of_uri, manager_node_uri)}
            r = requests.post(corese_url, params=payload)

            logging.info('[JOIN]New SensorAgent')

        elif join_type == 'client':
            # data = json.loads(self.request.body)

            client_id = uuid.uuid4()

            # if 'client-id' not in data:
            #     self.set_status(400)
            #     return
            # client_id = data['client-id']

            self.manager_node.consumers.append(str(client_id))

            payload = json.dumps({'client-id': str(client_id)})
            self.set_header('Content-Type', 'application/json')
            self.write(payload)

        else:
            self.set_status(400)
            return


class SubscribeHandler(tornado.web.RequestHandler):
    def initialize(self, manager_node):
        self.manager_node = manager_node

    def post(self):
        request_body = json.loads(self.request.body)
        query = request_body['query']
        subcribed_property = request_body['query']['property']

        if subcribed_property is None or query is None:
            self.set_status(400)
            return

        manager_url = 'http://{}:{}/coord/{}/{}'.format(self.manager_node.host, self.manager_node.port,
                                                        self.manager_node.context_dimension_type,
                                                        self.manager_node.domain_name)
        callback_url = None
        if 'callback_url' in request_body:
            callback_url = request_body['callback_url']

        resource = SubscribeResource(query, manager_url, subcribed_property, callback_url)

        self.manager_node.resources.append(resource)

        self.set_header('Content-Type', 'application/json')

        thing = query['things'][0]
        r = requests.get(thing + '/properties/available', params={'format':'json-ld'})

        availability = json.loads(r.content.decode('ascii'))['available']

        resource_data = resource.get_resource()
        if availability is True:
            resource_data['data']['data'] = 'available'
        else:
            resource_data['data']['data'] = 'unavailable'

        resource.update_resource(resource_data)

        self.manager_node.resources.append(resource)
        self.write(resource_data)


class ResourceHandler(tornado.web.RequestHandler):
    def initialize(self, manager_node):
        self.manager_node = manager_node

    def get(self, resource_id):
        if resource_id is None:
            # TODO send reason response
            self.set_status(400)
            return

        print(resource_id)

        resource = self.manager_node.get_resource(resource_id)

        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(resource.get_resource()))


class SubscribeResource:
    def __init__(self, query, manager_url, properties, callback_url=None):
        self.query = query
        self.callback_url = callback_url
        self.id = str(uuid.uuid4())
        self.manager_url = manager_url
        self.data = {'timestamp': time.time()}
        self.properties = properties

    def get_resource(self):
        resource = {}
        resource['data'] = self.data
        resource['id'] = self.id
        resource['query'] = self.query
        resource['url'] = '{}/resources/{}'.format(self.manager_url, self.id)
        resource['callback_url'] = self.callback_url
        resource['resource_type'] = self.properties

        return resource

    def update_resource(self, data=None):
        ts = time.time()
        self.data['timestamp'] = time.ctime(ts)

        if data is not None:
            self.data = data

        if self.callback_url is not None:
            self.send_update(data)

    def send_update(self, data):
        if self.callback_url is not None:
            payload = self.get_resource()
            try:
                r = requests.post(url=self.callback_url, json=payload)
            except:
                logging.info('Could not notify subscriber at url ' + self.callback_url)


class ManagerNode:
    def __init__(self, domain_name, context_dimension_type, port=7777, host='localhost'):
        self.domain_name = domain_name
        self.context_dimension_type = context_dimension_type
        self.port = port
        self.host = host
        self.base_uri = host + ':' + str(port) + '/'
        self.consumers = []
        self.sensor_nodes = []
        self.resources = []

        handlers = [(r"/coord/location/lab308", BaseHandler, dict(manager_node=self)),
                    (r"/coord/location/lab308/join", JoinHandler, dict(manager_node=self)),
                    (r"/coord/location/lab308/providers", ProvidersHandler, dict(manager_node=self)),
                    (r"/coord/location/lab308/capabilities", CapabilitiesHandler, dict(manager_node=self)),
                    (r"/coord/location/lab308/subscribe", SubscribeHandler, dict(manager_node=self)),
                    (r'/coord/location/lab308/resources/' + r'(?P<resource_id>[^/]+)', ResourceHandler,
                     dict(manager_node=self)),
                    (r'/coord/location/lab308/event_listener', EventListenerHandler, dict(manager_node=self))]

        self.application = tornado.web.Application(handlers)
        self.server = tornado.httpserver.HTTPServer(self.application)

    def get_resource(self, resource_id):
        resource = None
        for res in self.resources:
            if res.id == resource_id:
                resource = res

        return resource

    def resource_update(self, property, data):
        for resource in self.resources:
            resource_dict = resource.get_resource()
            if resource_dict['query']['property'] == property:
                for thing in resource_dict['query']['things']:
                    if data['thing'] == thing:
                        resource.update_resource(data)

    def as_ontology_description(self):
        td = owlready2.get_ontology(config['td_ontology_path']).load()
        context_domain = owlready2.get_ontology(config['contextDomain_ontology_path']).load()

        base = 'http://{}:{}/coord/{}/{}'.format(self.host, self.port, self.context_dimension_type, self.domain_name)

        if td.world.get(iri=base) is None:
            thing = td.Thing(iri=base)
            thing.is_a.append(context_domain.ContextDomainGroup)

            thing_context_dimension = context_domain.ContextDimension(self.domain_name)
            thing.hasDimension = [thing_context_dimension]

            providers_property = td.PropertyAffordance(iri=base + '/providers')
            capabilities_property = td.PropertyAffordance(iri=base + '/capabilities')

            thing.hasPropertyAffordance = [thing, providers_property, capabilities_property]

        graph = td.world.as_rdflib_graph()

        uri = rdflib.URIRef(td.base_iri + 'Thing')

        ontology_str = ''

        query = " CONSTRUCT {{ ?name ?hasProperty ?Property . ?Property ?hasData ?Data . }} WHERE {{ ?name ?hasProperty ?Property . ?Property ?hasData ?Data . ?name a <{}> }} ".format(
            uri)
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

    def as_thing_description(self):
        # TODO
        print()

    def get_capabilities_as_rdf(self):
        corese_url = config['corese_url']

        manages_thing = '<http://pervasive.semanticweb.org/ont/2019/07/consert/context-domain-org#managesThing>'
        query = ' select ?thing where {{?sensorNode {} ?thing}}'.format(manages_thing)
        payload = {'query': query}
        headers = {'Accept': 'application/sparql-results+csv'}
        r = requests.get(corese_url, params=payload, headers=headers)

        message = r.content.decode('ascii')

        lines = message.splitlines()
        lines.pop(0)

        graph = rdflib.Graph()
        rdf = rdflib.namespace.RDF

        bnode = rdflib.BNode()
        graph.add((bnode, rdf.type, rdf.Seq))

        for line in lines:
            rdf_object = rdflib.term.URIRef(line)
            graph.add((bnode, rdf.li, rdf_object))

        return graph.serialize(format='nt')

    def get_capabilities_as_td(self):
        # TODO
        print()

    def get_providers_as_rdf(self):
        # corese_url = config['corese_url']
        # manager_node_url = '<http://{}:{}/coord/{}/{}> '.format(self.host, self.port,
        #                                                         self.context_dimension_type,
        #                                                         self.domain_name)
        # group_member_of_url = '<http://pervasive.semanticweb.org/ont/2019/07/consert/context-domain-org#groupMemberOf> '
        #
        # query = ' select ?provider where {{?provider {} {}}}'.format(group_member_of_url, manager_node_url)
        # payload = {'query': query}
        # headers = {'Accept': 'application/sparql-results+csv'}
        # r = requests.get(corese_url, params=payload, headers=headers)
        #
        # message = r.content.decode('ascii')
        #
        # lines = message.splitlines()
        # lines.pop(0)
        #
        graph = rdflib.Graph()
        rdf = rdflib.namespace.RDF
        #
        bnode = rdflib.BNode()
        # graph.add((bnode, rdf.type, rdf.Seq))
        #
        # for line in lines:
        #     rdf_object = rdflib.term.URIRef(line)
        #     graph.add((bnode, rdf.li, rdf_object))

        for sensor_node in self.sensor_nodes:
            rdf_object = rdflib.term.URIRef(sensor_node)
            graph.add((bnode, rdf.li, rdf_object))

        return graph.serialize(format='nt')

    def get_providers_as_td(self):
        # TODO
        print()

    def start(self):
        self.server.listen(self.port, self.host)
        tornado.ioloop.IOLoop.current().start()

    def stop(self):
        self.server.stop()


def run_server():
    start_corese_server_thread()
    time.sleep(5)

    manager_node = ManagerNode(domain_name=config['domain_name'],
                               context_dimension_type=config['context_dimension_'
                                                             'type'], host=config['host'],
                               port=config['port'])
    try:
        logging.info('starting the server')
        manager_node.start()
    except KeyboardInterrupt:
        logging.info('stopping the server')
        manager_node.stop()
        logging.info('done')


if __name__ == '__main__':
    logging.basicConfig(
        level=20,
        # format="%(asctime)s %(filename)s:%(lineno)s %(levelname)s %(message)s"
        format="[MANAGER NODE]  %(asctime)s %(levelname)s %(message)s"
    )

    run_server()
