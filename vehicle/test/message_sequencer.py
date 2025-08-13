from enum import Enum

class Topic(Enum):
    SWARM_CONTROLLER = 1
    MISSION_SERVICE = 2
    DRIVER_CONTROL_SERVICE = 3

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
