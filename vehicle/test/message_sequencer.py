from enum import Enum

class Topic(Enum):
    SWARM_CONTROLLER = 1
    MISSION_SERVICE = 2
    DRIVER_SERVICE = 3
    COMPUTE_SERVICE = 4
    REPORT_SERVICE = 5

class MessageSequencer:
    '''
    Sequences messages sent over gRPC to test that the sequencing is correct.
    Messages are stored in a shared list, formatted: [(topic, message), ...]
    '''
    def __init__(self, topic, messages):
        self._topic = topic
        self._messages = messages

    def write(self, message):
        self._messages.append((self._topic, message.DESCRIPTOR.name))

def sequence_params(func):
    '''
    Decorator that writes a request to the message log when a request
    is received (must be the second argument). Assumes that the class
    has set a self.sequencer object.
    '''
    async def wrapper(*args):
        try:
            args[0].sequencer.write(args[1])
        except Exception as e:
            print(e) 
            raise ValueError("No self.sequencer object set!")
        await func(*args)
    return wrapper
