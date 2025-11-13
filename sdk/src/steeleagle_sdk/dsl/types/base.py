from typing import Any
from enum import Enum
from pydantic import BaseModel, ConfigDict
from ...api.datatypes._base import Datatype as BaseDatatype

class Action(BaseModel):
    '''
    Pydantic base model for actions (things you execute).
    '''
    # Lenient validation; allow non-pydantic objects in fields if needed
    model_config = ConfigDict(extra='forbid', arbitrary_types_allowed=True, ignored_types=(Enum,))

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
    model_config = ConfigDict(extra='forbid', arbitrary_types_allowed=True, ignored_types=(Enum,))

    async def check(self) -> Any:
        '''
        Check to see if the event has been completed.
        '''
        raise NotImplementedError

class Datatype(BaseDatatype):
    """Re-export of DataType from api._base as a local class."""
    pass
