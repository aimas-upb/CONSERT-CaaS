import json
import logging
import threading

import tornado.web
import tornado.ioloop
import tornado.httpserver
import requests


class CallbackHandler(tornado.web.RequestHandler):
    def post(self):
        message = json.loads(self.request.body)
        print(json.dumps(message, indent=4))


class Client:
    def __init__(self):
        handlers = [(r"/notify", CallbackHandler)]
        self.application = tornado.web.Application(handlers)
        self.server = tornado.httpserver.HTTPServer(self.application)
        self.running = False

    def subscribe(self, url):
        payload = {
            'query': {
                'property': 'Available',
                'things': [
                    'http://localhost:8888/0',
                    'http://localhost:8888/1'
                ]
            },
            'callback_url': 'http://localhost:7070/notify'
        }
        r = requests.post(url, json=payload)

    # example methods
    def get_capabilities(self, manager_node):
        """
        :param manager_node: URL of the ManagerNode
        :return: list of strings representing capabilities URLs
        """
        # TODO
        pass

    def get_thing_properties(self, thing):
        """
        :param thing: URL of the Thing
        :return: list of strings representing properties URLs
        """
        # TODO
        pass

    def get_property_value(self, property):
        """
        :param property: URL of the Property
        :return: dict as { property_name: property_value }
        """
        # TODO
        pass

    # server manage
    def start(self):
        self.running = True

        self.server.listen(7070, 'localhost')  # TODO hardcoded
        tornado.ioloop.IOLoop.current().start()

    def stop(self):
        self.running = False
        self.server.stop()


def run():
    client = Client()
    try:
        client.subscribe('http://localhost:7777/coord/location/lab308/subscribe')
    except:
        logging.warning('Unable to subscribe to ManagerNode')
    try:
        logging.info('Starting client')
        client.start()
    except KeyboardInterrupt:
        client.stop()


if __name__ == '__main__':
    logging.basicConfig(
        level=20,
        format="%(asctime)s %(filename)s:%(lineno)s %(levelname)s %(message)s"
    )

    run()
