from interfaces import CloudletItf
import json
import threading
import time

class ElijahCloudlet(CloudletItf.CloudletItf):

    def __init__(self, comm):
        self.engine_results = {}
        self.comm = comm

    def processResults(self, result_wrapper):
        result = json.loads(result_wrapper.payload.decode('utf-8'))
        producer = result_wrapper.getResultProducerName().getValue()
        self.engine_results[producer] = result

    def startStreaming(self, drone, model, sample_rate):
        self.stop = False

        def stream(self, sample_rate):
            while not self.stop:
                self.sendFrame(self.drone.getVideoFrame())
                time.sleep(1 / sample_rate)

        self.stream = threading.Thread(target=stream, args=(self, sample_rate, ))
        self.stream.start()

    def stopStreaming(self):
        self.stop = True
        self.stream.join()

    def sendFrame(self, frame):
        # Build extras here with drone items
        # TODO: Tom, I need your help to write this
        pass

    def getResults(self, engine_key):
        try:    
            return self.engine_results.pop(engine_key)
        except:
            return None
