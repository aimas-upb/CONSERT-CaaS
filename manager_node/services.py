import roslibpy
import threading
import time

class AvailabilityService:

    @staticmethod
    def check_availability(host, port):
        #TODO implementation
        print("Checking availability")

    @staticmethod
    def listen_avilability(thing, client):

        #TODO change service name to something relevant
        service = roslibpy.Service(client, '/set_ludicrous_speed', 'std_srvs/SetBool')

        service.advertise(thing.set_availability)

        x = threading.Thread(target=client.run())
        x.start()
        print("Sarted listening availability for: " + thing.name)


class ActuationService:
    @staticmethod
    def ros_actuation(thing, talker, data):
        talker.publish(roslibpy.Message({'data': data}))
