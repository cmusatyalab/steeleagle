import asyncio
from typing import Any, Dict
from pydantic import BaseModel, ConfigDict
from dataclasses import dataclass

class Action(BaseModel):
    '''
    Pydantic base model for actions (things you execute).
    '''
    # Lenient validation; allow non-pydantic objects in fields if needed
    model_config = ConfigDict(extra='forbid', arbitrary_types_allowed=True)

    async def execute(self) -> Any:
        '''
        Execute the action asynchronously.
        '''
        raise NotImplementedError

class Event(BaseModel):
    '''
    Pydantic base model for events (things you wait/observe).
    '''
    # Lenient validation; allow non-pydantic objects in fields if needed
    model_config = ConfigDict(extra='forbid', arbitrary_types_allowed=True)

    async def check(self) -> bool:
        '''
        Check to see if the event has been completed.
        '''
        raise NotImplementedError

@dataclass
class Datatype(BaseModel):
    '''
    Pydantic base model for a Protobuf message.
    '''
    # Lenient validation; allow non-pydantic objects in fields if needed
    model_config = ConfigDict(extra='forbid', arbitrary_types_allowed=True)

    def get_type_url() -> str:
        '''
        Get the type url associated with the object (from Protobuf specification).
        This is useful for unpacking/packing the object as an Any.
        '''
        raise NotImplementedError
