import roslibpy
import threading
import time


class AvailabilityService:
    def __init__(self, thing):
        self.thing = thing

    def check_availability(self):
        raise NotImplementedError

    def listen_availability(self):
        """
        service = roslibpy.Service(self.client, '/set_ludicrous_speed', 'std_srvs/SetBool')
        request = roslibpy.ServiceRequest({'data': True})

        print('Calling service...')
        result = service.call(request)
        print('Service response: {}'.format(result))
        """
        raise NotImplementedError


class ActuationService:
    def __init__(self, thing):
        self.thing = thing

    def ros_actuation(self, payload):
        raise NotImplementedError
