from enum import Enum
from pydantic import BaseModel, ConfigDict


class Datatype(BaseModel):
    """
    Pydantic base model for a Protobuf message.
    """

    # Lenient validation; allow non-pydantic objects in fields if needed
    model_config = ConfigDict(
        extra="forbid", arbitrary_types_allowed=True, ignored_types=(Enum,)
    )
