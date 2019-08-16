import logging
import subprocess
import threading

import rdflib
import requests
import time

import owlready2

import tornado.web
import tornado.ioloop
import tornado.httpserver
import yaml

stream = open('managernode_config.yaml')
config = yaml.load(stream)


def start_corese_server(corese_server_path):
    # subprocess.call(['java', '-jar', corese_server_path])
    subprocess.call(['java', '-jar', '-Dlog4j.configurationFile=file:{}'.format(config['corese_Dlog4j_config_file']), corese_server_path])
    # TODO find a way to test if it launched successfully


def load_ontology(url):
    r = requests.get(url)


def start_corese_server_thread():
    corese_server_path = config['corese_server_path']
    corese_server_thread = threading.Thread(target=start_corese_server, args=(corese_server_path,))
    corese_server_thread.start()


class BaseHandler(tornado.web.RequestHandler):
    def initialize(self, manager_node):
        self.manager_node = manager_node

    def get(self):
        description = self.manager_node.as_ontology_description()
        self.write(description)


class ProvidersHandler(tornado.web.RequestHandler):

    def initialize(self, manager_node):
        self.manager_node = manager_node

    def get(self):
        corese_url = config['corese_url']
        manager_node_url = '<http://{}:{}/coord/{}/{}> '.format(self.manager_node.host, self.manager_node.port, self.manager_node.context_dimension_type, self.manager_node.domain_name)
        group_member_of_url = '<http://pervasive.semanticweb.org/ont/2019/07/consert/context-domain-org#groupMemberOf> '

        query = ' select ?provider where {{?provider {} {}}}'.format(group_member_of_url, manager_node_url)
        payload = {'query': query}
        headers = {'Accept': 'application/sparql-results+csv'}
        r = requests.get(corese_url, params=payload, headers=headers)

        message = r.content.decode('ascii')

        lines = message.splitlines()
        lines.pop(0)

        graph = rdflib.Graph()
        rdf = rdflib.namespace.RDF

        bnode = rdflib.BNode()
        graph.add( (bnode, rdf.type, rdf.Seq) )

        for line in lines:
            rdf_object = rdflib.term.URIRef(line)
            graph.add( (bnode, rdf.li, rdf_object) )

        self.write(graph.serialize(format='nt'))


class CapabilitiesHandler(tornado.web.RequestHandler):
    def get(self):
        corese_url = config['corese_url']

        manages_thing = '<http://pervasive.semanticweb.org/ont/2019/07/consert/context-domain-org#managesThing>'
        query = ' select ?thing where {{?sensorNode {} ?thing}}'.format(manages_thing)
        payload = {'query': query}
        headers = {'Accept': 'application/sparql-results+csv'}
        r = requests.get(corese_url, params=payload, headers = headers)

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

        self.write(graph.serialize(format='nt'))


class JoinHandler(tornado.web.RequestHandler):

    def initialize(self, manager_node):
        self.manager_node = manager_node

    def post(self):
        new_data = self.request.body.decode(encoding='ascii')

        corese_url = config['corese_url']

        for line in new_data.splitlines():
            payload = {'query' : 'INSERT DATA{{ {} }}'.format(line)}
            r = requests.post(corese_url, params=payload)

        manager_node_uri = '<http://{}:{}/coord/{}/{}> '.format(self.manager_node.host, self.manager_node.port, self.manager_node.context_dimension_type, self.manager_node.domain_name)
        sensor_node_uri = '<http://localhost:8888> '   # TODO hardcoded
        group_member_of_uri = '<http://pervasive.semanticweb.org/ont/2019/07/consert/context-domain-org#groupMemberOf> '
        payload = {'query' : 'INSERT DATA{{ {} {} {} }}'.format(sensor_node_uri, group_member_of_uri, manager_node_uri)}
        r = requests.post(corese_url, params=payload)

        logging.info('[JOIN]New SensorAgent')
        self.write("React to post request")


class ManagerNode:
    def __init__(self, domain_name, context_dimension_type, port = 7777, host = 'localhost'):
        self.domain_name = domain_name
        self.context_dimension_type = context_dimension_type
        self.port = port
        self.host = host
        self.base_uri = host + ':' + str(port) + '/'

        handlers = [(r"/coord/location/lab308", BaseHandler, dict(manager_node = self)),
                    (r"/coord/location/lab308/join", JoinHandler, dict(manager_node = self)),
                    (r"/coord/location/lab308/providers", ProvidersHandler, dict(manager_node = self)),
                    (r"/coord/location/lab308/capabilities", CapabilitiesHandler)]

        self.application = tornado.web.Application(handlers)
        self.server = tornado.httpserver.HTTPServer(self.application)

    def as_ontology_description(self):
        td = owlready2.get_ontology(config['td_ontology_path']).load()
        context_domain = owlready2.get_ontology(config['contextDomain_ontology_path']).load()

        base = 'http://{}:{}/coord/{}/{}'.format(self.host, self.port, self.context_dimension_type, self.domain_name)

        if td.world.get(iri = base) is None:
            thing = td.Thing(iri = base)
            thing.is_a.append(context_domain.ContextDomainGroup)

            thing_context_dimension = context_domain.ContextDimension(self.domain_name)
            thing.hasDimension = [thing_context_dimension]

            providers_property = td.PropertyAffordance(iri = base + '/providers')
            capabilities_property = td.PropertyAffordance(iri = base + '/capabilities')

            thing.hasPropertyAffordance = [thing, providers_property, capabilities_property]

        graph = td.world.as_rdflib_graph()

        uri = rdflib.URIRef(td.base_iri + 'Thing')

        ontology_str = ''

        query = " CONSTRUCT {{ ?name ?hasProperty ?Property . ?Property ?hasData ?Data . }} WHERE {{ ?name ?hasProperty ?Property . ?Property ?hasData ?Data . ?name a <{}> }} ".format(uri)
        # query = " CONSTRUCT { ?name ?hasProperty ?Property} WHERE { ?name ?hasProperty ?Property . } "
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

    def start(self):
        self.server.listen(self.port, self.host)
        tornado.ioloop.IOLoop.current().start()

    def stop(self):
        self.server.stop()


def run_server():
    start_corese_server_thread()
    time.sleep(5)
    # load_ontology("http://localhost:8080/sparql/load --post-data='remote_path=file:///home/costin/Desktop/AI-MAS/CONSERT-CaaS/ontology/td.ttl'")
    # load_ontology("http://localhost:8080/sparql/load --post-data='remote_path=file:///home/costin/Desktop/AI-MAS/CONSERT-CaaS/ontology/lab308.ttl'")

    manager_node = ManagerNode(domain_name=config['domain_name'], context_dimension_type=config['context_dimension_type'], host=config['host'], port=config['port'])
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
