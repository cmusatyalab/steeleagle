from abc import ABC, abstractmethod
from enum import Enum

    
class ComputeInterface(ABC):
    class ComputeStatus(Enum):
        Connected = 1
        Disconnected = 2
        IDLE = 3
        
    def __init__(self, compute_id):
        self.compute_id = compute_id
        self.compute_status = self.ComputeStatus.IDLE
        

    @abstractmethod
    async def run(self):
        """Running the worker."""
        pass
    
    @abstractmethod
    def stop(self):
        """Stopping the worker."""
        pass
    
    @abstractmethod
    def getStatus(self):
        """Getting the status of the worker."""
        pass
     

    @abstractmethod
    def set(self):
        """Setting the metadata of the worker."""
        pass