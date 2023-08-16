from abc import ABC, abstractmethod

class CloudletItf(ABC):

    @abstractmethod
    def processResults(self, result_wrapper):
        pass

    @abstractmethod
    def startStreaming(self, drone, model, sample_rate):
        pass

    @abstractmethod
    def stopStreaming(self):
        pass

    @abstractmethod
    def switchModel(self, model):
        pass

    @abstractmethod
    def sendFrame(self, frame):
        pass

    @abstractmethod
    def getResults(self, engine_key):
        pass
